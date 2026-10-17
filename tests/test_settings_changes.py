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


def test_a_write_announced_by_itself_fires_only_what_it_noted_and_a_quiet_one_is_never_fired(tmp_path, monkeypatch):
    """UX recheck 2026-10-17: a long-running process's write announced alone carries its own tables and concerns, never
    another write's; one its caller announces itself is fired by nothing else, the command's end included."""
    from metaform import events
    fired = []
    monkeypatch.setattr(events, 'publish', lambda topic, payload, source: fired.append(payload) or [])
    changes.take()
    changes.note('p', 'b', {'dispatch.catalog'})  # another write's, saying nothing of what it concerns
    changes.quietly(changes.note, 'p', 'b', {'dispatch.session_lines'})
    _, payloads = changes.announced(tmp_path, 'cli', changes.note, 'p', 'b', {'work'}, 7,
                                    {'work_ids': {'w'}, 'kinds': {'ticket'}})
    assert payloads == fired == [{'project': 'p', 'base_id': 'b', 'tables': ['work'], 'seq': 7, 'work_ids': ['w'],
                                  'session_ids': [], 'kinds': ['ticket']}]
    assert changes.take() == {'p': {'b': {'dispatch.catalog'}}}
