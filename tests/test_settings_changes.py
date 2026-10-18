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


def _fresh(path):
    """The dispatch tables gone from a store, and their record, as on a project no agent has started in."""
    import sqlite3
    with sqlite3.connect(path) as db:
        names = [name for (name,) in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'dispatch%'")]
        for name in names:
            db.execute(f'DROP TABLE "{name}"')
        db.execute("DELETE FROM meta WHERE key LIKE '%dispatch'")


def test_a_module_s_tables_made_on_first_touch_are_no_change_and_never_erase_a_write_s_concerns(run, tmp_path):
    """UX recheck 2026-10-17 at b410f6a5: installing dispatch's tables on a fresh project, for a read or inside its
    first write, notes neither `meta` nor `sqlite_master`, so the write's tables and tickets reach the page whole, and a
    first write that changed no row but the install's notes nothing."""
    from metaform.data import Node, Store
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    run('enable', 'map')
    run('enable', 'dispatch')
    store = Store('proj')
    store.layer('parts', 'test', 'The parts.', mutable=True, hideable=True, ready=True)
    store.add_element('parts', 'code.part')
    work = store.add_work(Node('element', 'code.part'), 'unbuilt', task='a task').id
    base = registry.active_base('proj')
    path = registry.store_file('proj', base.name)
    _fresh(path)
    changes.take()
    with Store('proj', module='dispatch').tables(write=False) as tx:
        assert tx.get('ticket_options', {'work_id': work}) is None
    assert 'proj' not in changes.take()
    _fresh(path)
    changes.take()
    with Store('proj', module='dispatch').tables() as tx:
        tx.concern(work_id=work, kind='ticket')
        tx.insert('ticket_options', {'work_id': work, 'model': 'm', 'seq': 1})
    assert changes.take() == {'proj': {base.id: {'dispatch.ticket_options'}}}
    assert changes.concerns('proj', base.id)['work_ids'] == [work]
    _fresh(path)  # a first write that changes no row of its own, as a start's launch options with none given
    changes.take()
    with Store('proj', module='dispatch').tables() as tx:
        tx.delete('ticket_options', {'work_id': work})
    assert 'proj' not in changes.take()
