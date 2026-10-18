"""Installed BMAD entry points stay source-aware, optional, and on public managed-call paths."""
from __future__ import annotations

import hashlib

import pytest

from metaform.data import Node, prompts
from metaform.module import context, resolve_agent_role
from metaform.modules.orchestration.state import SERVICE, verb
from tests.storekit import small_map

pytestmark = pytest.mark.kind('simulation')


def installed_manifest(folder):
    config = folder / '_bmad/_config'
    config.mkdir(parents=True)
    (config / 'manifest.yaml').write_text('installation:\n  version: fixture-installed-version\n', encoding='utf-8')
    (config / 'agent-manifest.csv').write_text(
        'name,title,module,path\ndev,Developer,bmm,_bmad/bmm/agents/dev.md\n', encoding='utf-8')
    source = folder / '_bmad/bmm/agents/dev.md'
    source.parent.mkdir(parents=True)
    source.write_text('''# Installed developer
<activation>Read the installed configuration and use the supplied menu input.</activation>
<menu><item cmd="CR">Review the candidate using the installed review procedure.</item></menu>
Return the review evidence to the immediate caller.
''', encoding='utf-8')
    return source


def test_optional_installation_does_not_hide_native_role_or_invent_bmad(project_folder, store):
    called = context('orchestration', project_folder, project='proj')
    inspected = verb(called, 'orchestration', 'bmad')
    assert not inspected['installed']
    assert inspected['roles'] == []
    assert not resolve_agent_role(project_folder, 'gc', project='proj')['problems']
    unknown = resolve_agent_role(project_folder, 'bmad.bmm.dev', project='proj')
    assert unknown['missing']


def test_manifest_role_source_versions_menu_override_and_managed_call(project_folder, store):
    small_map(store)
    source = installed_manifest(project_folder)
    called = context('orchestration', project_folder, project='proj')
    inspected = verb(called, 'orchestration', 'bmad')
    entry = inspected['roles'][0]
    assert entry['name'] == 'bmad.bmm.dev'
    assert entry['source'] == str(source)
    assert entry['source_fingerprint'] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert entry['installed_version'] == 'fixture-installed-version'
    assert 'cmd="CR"' in entry['menu']
    initial = resolve_agent_role(project_folder, entry['name'], project='proj')
    assert not initial['problems']
    assert source.read_text() in initial['text']
    assert str(source.parent) in initial['text']
    first_version = initial['components'][-1]['actual_version_id']

    source.write_text(source.read_text().replace('review evidence', 'candidate-specific interaction evidence'),
                      encoding='utf-8')
    updated = resolve_agent_role(project_folder, entry['name'], project='proj')
    assert updated['components'][-1]['actual_version_id'] != first_version
    history = prompts.prompt_versions(entry['prompt'])
    assert len(history) == 2
    assert next(one for one in history if one.version_id != first_version).parent_id == first_version
    edited = prompts.save_prompt(entry['prompt'], '# User register retained.\n'
        '<menu><item cmd="UX">Observe the complete timer interaction.</item></menu>')
    source.write_text(source.read_text() + '\nInstalled upstream update.\n', encoding='utf-8')
    selected = verb(called, 'orchestration', 'bmad')['roles'][0]
    assert selected['selected_version_id'] == selected['actual_version_id'] == edited.version_id
    assert selected['selected_origin'] == 'edited'
    assert 'cmd="UX"' in selected['menu']
    assert 'cmd="CR"' in selected['source_menu']
    actual = resolve_agent_role(project_folder, entry['name'], project='proj')
    assert 'User register retained.' in actual['text']
    assert 'Installed upstream update.' not in actual['text']

    ticket = store.add_work(Node('element', 'code.timer.kitchen'), None,
                            task='Preserve the timer interaction.', title='Timer delivery')
    gc = SERVICE.claim(context('orchestration', project_folder, project='proj', session='gc',
                               nouns={'work': ticket.id}))
    specialist = verb(context('orchestration', project_folder, project='proj', session='gc'),
        'orchestration', 'call', role=entry['name'], task='UX: observe the full timer adjustment.',
        result='Return the observed constraints.', context={'candidate': 'installed-candidate'}, key='bmad-review')
    assert specialist['authored_role_uri'] == entry['uri']
    assert specialist['return_to']['assignment_id'] == gc['assignment_id']
    assert 'UX: observe the full timer adjustment.' in specialist['task']
    assert 'installed-candidate' in specialist['task']
    assert SERVICE.assignment(called, work_id=gc['work_id'])['state'] == 'waiting'
    pending = SERVICE.pending(called)
    assert any(one['kind'] == 'suspend' and one['assignment_id'] == gc['assignment_id'] for one in pending)
    assert any(one['kind'] == 'launch' and one['assignment_id'] == specialist['assignment_id'] for one in pending)
    source.unlink()
    absent = resolve_agent_role(project_folder, entry['name'], project='proj')
    assert not absent['missing']  # unavailable installed source is not a request to invent a replacement role
    assert 'unavailable' in absent['problems'][0]


def test_installed_skill_entry_points_menu_source_conflicts_and_exact_version(project_folder, store):
    source = project_folder / '.agents/skills/bmad-agent-architect/SKILL.md'
    source.parent.mkdir(parents=True)
    source.write_text('''---
name: bmad-agent-architect
description: Installed architecture consultation.
version: skill-source-version
---
# Menu
- DA: Discuss architecture using installed procedures.

# Activation
Follow the selected menu input.
''', encoding='utf-8')
    called = context('orchestration', project_folder, project='proj')
    entry = verb(called, 'orchestration', 'bmad')['roles'][0]
    assert entry['name'] == 'bmad.skill.architect'
    assert entry['installed_version'] == 'skill-source-version'
    assert entry['format'] == 'installed-skill'
    assert 'DA:' in entry['menu']
    duplicate = project_folder / '.claude/skills/bmad-agent-architect/SKILL.md'
    duplicate.parent.mkdir(parents=True)
    duplicate.write_bytes(source.read_bytes())
    assert not resolve_agent_role(project_folder, entry['name'], project='proj')['problems']
    duplicate.write_text(source.read_text() + '\nDifferent installed architecture procedure.\n', encoding='utf-8')
    conflict = resolve_agent_role(project_folder, entry['name'], project='proj')
    assert not conflict['missing']
    assert 'claimed by providers' in conflict['problems'][0]
