"""Setting writes notify related projects after commit, without naming a module."""
import pytest

from metaform import changes
from metaform import home as registry

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('BASE-053')]


@pytest.mark.parametrize('operation', ['save', 'clear'])
@pytest.mark.parametrize('scope', ['global', 'ancestor', 'project', 'child'])
def test_setting_changes_name_owner_for_related_projects(home, tmp_path, operation, scope):
    source = tmp_path / 'source'
    project = source / 'project'
    project.mkdir(parents=True)
    unrelated = tmp_path / 'unrelated'
    unrelated.mkdir()
    registry.add_project('p', project)
    registry.add_project('other', unrelated)
    changed_scope = 'global' if scope == 'global' else registry.path_key(
        {'ancestor': source, 'project': project, 'child': project / 'child'}[scope])
    changes.take()
    if operation == 'save':
        registry.save(changed_scope, 'example', 'option', [True])
    else:
        registry.clear(changed_scope, 'example', 'option')
    noted = changes.take()
    expected = {'p', 'other'} if scope == 'global' else {'p'}
    assert set(noted) == expected
    assert all(value == {'': {'example.settings'}} for value in noted.values())
