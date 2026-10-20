"""Native skill deployment ownership and fallback detection, BASE-059."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from metaform import install

pytestmark = [pytest.mark.kind('simulation'), pytest.mark.req('BASE-059')]


@pytest.fixture
def deployment(home, tmp_path, monkeypatch):
    user = tmp_path / 'user'
    user.mkdir()
    monkeypatch.setattr(install, 'user_home', lambda: user)
    monkeypatch.setenv('METAFORM_WHEEL', '')
    monkeypatch.setattr(install, 'server', lambda folder: None)
    monkeypatch.setattr(install, 'http_url', lambda folder, command: None)
    monkeypatch.setattr(install, '_agent_changes', lambda names, **kwargs: {name: [] for name in names})
    tool = install.Tool('cursor', 'Cursor', lambda: True, 'test', lambda: user / '.cursor/mcp.json',
                        lambda: user / '.cursor/skills', merge=True)
    monkeypatch.setattr(install, 'tools', lambda: {'cursor': tool})
    catalog = [SimpleNamespace(name=name, address=f'prompt.skill.{name}', discover=discover, version='1',
                               requires=('axiom',), tier='workflow', folder=tmp_path / name)
               for name, discover in [('write-workflow', True), ('import-workflow', True),
                                      ('sentinel', False), ('workflow-evaluator', False)]]
    contents = {'SKILL.md': b'entry', 'references/procedure.axiom': b'procedure',
                'references/axiom.axiom': b'fresh library'}
    stub = SimpleNamespace(catalog=lambda: catalog, deployment_files=lambda skill: dict(contents))
    monkeypatch.setitem(sys.modules, 'metaform.skills', stub)
    monkeypatch.setattr(sys.modules['metaform'], 'skills', stub, raising=False)
    output = []
    return SimpleNamespace(user=user, home=home, root=user / '.cursor/skills', tool=tool,
                           catalog=catalog, contents=contents, output=output)


def test_install_deploys_discoverable_skills_with_libraries_and_records_exact_files(deployment):
    install.install(['cursor'], deployment.output.append)
    for name in ('write-workflow', 'import-workflow'):
        for relative, value in deployment.contents.items():
            assert (deployment.root / name / relative).read_bytes() == value
    assert not (deployment.root / 'sentinel').exists()
    assert not (deployment.root / 'workflow-evaluator').exists()
    assert (deployment.root / 'metaform/SKILL.md').read_bytes() == install.skill_text()
    assert install.skills_deployed('Cursor')
    library = str(deployment.root / 'write-workflow/references/axiom.axiom')
    assert any(library in line for line in deployment.output)
    assert not install.skills_deployed('unknown-client')
    assert not install.skills_deployed('Claude Code')


def test_changed_library_missing_file_and_changed_catalog_keep_fallback_index(deployment):
    install.install(['cursor'], deployment.output.append)
    assert install.skills_deployed('cursor')
    deployment.contents['references/axiom.axiom'] = b'new library'
    assert not install.skills_deployed('cursor')
    install.install(['cursor'], deployment.output.append)
    assert install.skills_deployed('cursor')
    (deployment.root / 'write-workflow/SKILL.md').unlink()
    assert not install.skills_deployed('cursor')
    install.install(['cursor'], deployment.output.append)
    deployment.catalog[0].version = '2'
    assert not install.skills_deployed('cursor')


def test_uninstall_keeps_unrelated_and_modified_files_and_backs_up_owned_removals(deployment):
    existing = deployment.root / 'write-workflow/SKILL.md'
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b'previous skill')
    install.install(['cursor'], deployment.output.append)
    assert any(path.read_bytes() == b'previous skill' for path in
               (deployment.home / 'backups/install').rglob('SKILL.md'))
    unrelated = existing.parent / 'personal.md'
    unrelated.write_text('mine')
    modified = existing.parent / 'references/procedure.axiom'
    modified.write_text('my changes')
    install.uninstall(['cursor'], deployment.output.append)
    assert unrelated.read_text() == 'mine'
    assert modified.read_text() == 'my changes'
    assert not existing.exists()
    assert not (deployment.root / 'import-workflow').exists()
    assert not install.skills_deployed('cursor')
    assert any(path.read_bytes() == b'entry' for path in
               (deployment.home / 'backups/uninstall').rglob('SKILL.md'))


def test_copy_failure_never_records_a_complete_deployment(deployment, monkeypatch):
    original = Path.write_bytes

    def write(path, data):
        if path == deployment.root / 'write-workflow/references/procedure.axiom':
            raise OSError('disk full')
        return original(path, data)

    monkeypatch.setattr(Path, 'write_bytes', write)
    with pytest.raises(OSError, match='disk full'):
        install.install(['cursor'], deployment.output.append)
    assert not install.skills_deployed('cursor')
    install.uninstall(['cursor'], deployment.output.append)
    assert not (deployment.root / 'write-workflow/SKILL.md').exists()


def test_upgrade_removes_retired_owned_files_and_keeps_personal_files(deployment):
    install.install(['cursor'], deployment.output.append)
    personal = deployment.root / 'import-workflow/personal.md'
    personal.write_text('mine')
    deployment.catalog[:] = [skill for skill in deployment.catalog if skill.name != 'import-workflow']
    deployment.contents.pop('references/axiom.axiom')
    deployment.output.clear()
    install.install(['cursor'], deployment.output.append)
    assert personal.read_text() == 'mine'
    assert not (deployment.root / 'import-workflow/SKILL.md').exists()
    assert not (deployment.root / 'write-workflow/references/axiom.axiom').exists()
    removed = str(deployment.root / 'import-workflow/SKILL.md')
    assert any('skill: remove' in line and removed in line for line in deployment.output)
    assert install.skills_deployed('cursor')


@pytest.mark.parametrize('name,verified,has_skills', [('other', True, True), ('cursor', True, False)])
def test_only_harnesses_known_to_discover_skills_are_deployed(deployment, monkeypatch, name, verified, has_skills):
    tool = install.Tool(name, name, lambda: True, 'test', lambda: None,
                        lambda: deployment.root if has_skills else None, verified=verified)
    monkeypatch.setattr(install, 'tools', lambda: {name: tool})
    install.install([name], deployment.output.append)
    assert not (deployment.root / 'write-workflow').exists()
    assert not install.skills_deployed(name)


def test_client_names_match_only_known_native_harnesses(deployment, monkeypatch):
    original = deployment.tool
    for name, aliases in [('claude', ['Claude Code', 'claude-code']), ('codex', ['Codex', 'codex-mcp-client']),
                          ('gemini', ['Gemini CLI', 'gemini-cli'])]:
        tool = install.Tool(name, name, lambda: True, 'test', lambda: None, lambda: deployment.root)
        monkeypatch.setattr(install, 'tools', lambda name=name, tool=tool: {name: tool})
        install.install([name], deployment.output.append)
        for client in aliases:
            assert install.skills_deployed(client)
        assert not install.skills_deployed(f'unrelated-{name}-client')
        install.uninstall([name], deployment.output.append)
    monkeypatch.setattr(install, 'tools', lambda: {'cursor': original})


def test_corrupt_record_keeps_fallback_index(deployment):
    from metaform import home
    home.set_meta('skill_deployment.cursor', json.dumps({'files': []}))
    assert not install.skills_deployed('cursor')
