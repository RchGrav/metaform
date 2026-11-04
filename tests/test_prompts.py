"""Prompts: versioned records in the home's prompt store, and the version each layer was made from, STORE-044."""
from __future__ import annotations

import json
import sqlite3

import pytest

pytestmark = pytest.mark.kind('fixture')


def row(home, version_id):
    db = sqlite3.connect(home / 'prompts.sqlite3')
    try:
        return db.execute('SELECT * FROM prompt_versions WHERE version_id=?', (version_id,)).fetchone()
    finally:
        db.close()


@pytest.mark.req('STORE-044')
def test_an_edit_adds_the_next_version_and_never_changes_the_one_it_came_from(home):
    from metaform.data import prompts
    first = prompts.add_prompt('practices', 'markdown', 'Write one practice per join.')
    second = prompts.add_prompt_version('practices', 'Write one practice per join, as an imperative.', first.number)
    third = prompts.add_prompt_version('practices', 'Write practices, each an imperative.', second.number)
    kept = row(home, third.version_id)
    fourth = prompts.add_prompt_version('practices', 'Write practices, each an imperative with a reason.', 3)
    assert (first.number, second.number, third.number, fourth.number) == (1, 2, 3, 4)
    assert fourth.parent_id == third.version_id and fourth.origin == 'edited'
    assert row(home, third.version_id) == kept
    assert prompts.prompt_version('practices', 3).text == 'Write practices, each an imperative.'
    assert prompts.prompt_version('practices').number == 4
    assert [version.number for version in prompts.prompt_versions('practices')] == [4, 3, 2, 1]
    same = prompts.add_prompt_version('practices', fourth.text, 4)
    assert same.version_id == fourth.version_id and [notice.where for notice in same.notices] == ['text']
    assert [(prompt.name, prompt.format, prompt.newest) for prompt in prompts.prompts()] == [
        ('practices', 'markdown', 4)]


@pytest.mark.req('STORE-044')
@pytest.mark.req('STORE-016')
def test_a_layer_stays_linked_to_the_version_it_was_made_from(home):
    from metaform.data import prompts
    prompts.add_prompt('practices', 'markdown', 'one')
    prompts.add_prompt_version('practices', 'two', 1)
    third = prompts.add_prompt_version('practices', 'three', 2)
    prompts.record_use(third.version_id, 'proj', 'metaform-1', 'layer-1')
    prompts.add_prompt_version('practices', 'four', 3)
    assert [(use.project_id, use.base_id, use.layer_id) for use in prompts.layers_by_prompt_version(
        third.version_id)] == [('proj', 'metaform-1', 'layer-1')]
    assert prompts.use_of('proj', 'metaform-1', 'layer-1').number == 3
    assert prompts.use_of('proj', 'metaform-1', 'layer-2') is None


@pytest.mark.req('STORE-044')
def test_a_shipped_prompt_flows_in_until_someone_saves_an_edit(home):
    from metaform.data import prompts
    first = prompts.shipped('practices', 'xml', '<process>A</process>')
    assert (first.number, first.origin) == (1, 'shipped')
    assert prompts.shipped('practices', 'xml', '<process>A</process>').version_id == first.version_id
    second = prompts.shipped('practices', 'xml', '<process>B</process>')
    assert (second.number, second.origin, second.parent_id) == (2, 'shipped', first.version_id)
    edited = prompts.add_prompt_version('practices', '<process>B, edited</process>', 2)
    kept = prompts.shipped('practices', 'xml', '<process>C</process>')
    assert kept.version_id == edited.version_id and kept.text == '<process>B, edited</process>'
    assert [version.number for version in prompts.prompt_versions('practices')] == [3, 2, 1]


@pytest.mark.req('STORE-044')
@pytest.mark.req('STORE-005')
def test_every_prompt_read_but_the_list_of_prompts_is_answered_through_an_index(home, traced):
    from metaform.data import prompts
    prompts.add_prompt('practices', 'markdown', 'one')
    second = prompts.add_prompt_version('practices', 'two', 1)
    prompts.record_use(second.version_id, 'proj', 'metaform-1', 'layer-1')
    reads = {'prompt_version': lambda: prompts.prompt_version('practices', 1),
             'newest': lambda: prompts.prompt_version('practices'),
             'prompt_versions': lambda: prompts.prompt_versions('practices'),
             'layers_by_prompt_version': lambda: prompts.layers_by_prompt_version(second.version_id),
             'use_of': lambda: prompts.use_of('proj', 'metaform-1', 'layer-1')}
    db = sqlite3.connect(home / 'prompts.sqlite3')
    for name, read in reads.items():
        traced.clear()
        read()
        issued = [statement for statement in traced if statement.lstrip().upper().startswith('SELECT')]
        assert issued, name
        for statement in issued:
            plan = [line[3] for line in db.execute('EXPLAIN QUERY PLAN ' + statement)]
            assert not [line for line in plan if line.startswith('SCAN ') and 'meta' not in line], (name, plan)
    db.close()


@pytest.mark.req('STORE-044')
@pytest.mark.req('CLI-031')
def test_prompts_and_prompt_list_and_show_the_stored_versions(run, home):
    from metaform.data import prompts
    prompts.add_prompt('practices', 'markdown', 'one\n')
    prompts.add_prompt_version('practices', 'two\n', 1)
    assert run('prompts').stdout == 'practices  markdown  version 2\n'
    assert run('prompt', 'practices').stdout == 'two\n'
    assert run('prompt', 'practices', '1').stdout == 'one\n'
    missing = run('prompt', 'nothing', ok=False)
    assert missing.returncode != 0 and missing.stderr.splitlines()[-1] == 'Next: metaform prompts'


@pytest.mark.req('STORE-044')
def test_prompt_save_preserves_text_versions_parents_and_layer_provenance(run, home):
    from metaform.data import prompts
    text = 'name=value\nReview café {target}.\n'
    first = json.loads(run('prompt', 'save', 'review', text, 'format=markdown', '--json').stdout)
    assert first['number'] == 1 and first['text'] == text and first['format'] == 'markdown'
    kept = row(home, first['version_id'])
    prompts.record_use(first['version_id'], 'project', 'map', 'layer')
    second = json.loads(run('prompt', 'save', 'review', '-', '--json', input='New text\n').stdout)
    assert second['number'] == 2 and second['parent_id'] == first['version_id']
    assert second['format'] == 'markdown'
    assert run('prompt', 'review', '1').stdout == text
    assert run('prompt', 'review').stdout == 'New text\n'
    assert row(home, first['version_id']) == kept
    assert prompts.use_of('project', 'map', 'layer').version_id == first['version_id']
    branch = prompts.save_prompt('review', 'Branch', parent=1)
    assert branch.number == 3 and branch.parent_id == first['version_id']
    same = prompts.save_prompt('review', 'Branch')
    assert same.version_id == branch.version_id and same.notices


@pytest.mark.req('STORE-044')
def test_prompt_save_rejects_unknown_parent_without_creating_a_prompt(home):
    from metaform.data import StoreError, prompts
    with pytest.raises(StoreError, match='has no version 2'):
        prompts.save_prompt('missing', 'text', parent=2)
    assert not prompts.prompts()
    prompts.save_prompt('existing', 'one')
    with pytest.raises(StoreError, match='has no version 3'):
        prompts.save_prompt('existing', 'two', parent=3)
    assert len(prompts.prompt_versions('existing')) == 1


@pytest.mark.req('CLI-009')
def test_prompt_save_invalid_parent_uses_the_regular_validation_error(run):
    invalid = run('prompt', 'save', 'review', 'Text', 'parent=²', ok=False)
    assert invalid.returncode == 2
    assert invalid.stderr.splitlines() == [
        'Error: parent= takes a positive version number.', 'Next: metaform help prompt']


@pytest.mark.req('STORE-044')
def test_a_shipped_change_behind_an_edit_is_kept_beside_it_until_the_shipped_text_comes_back(home):
    from metaform.data import prompts
    prompts.shipped('practices', 'xml', 'A')
    edited = prompts.save_prompt('practices', 'A, edited')
    assert prompts.shipped('practices', 'xml', 'A').version_id == edited.version_id
    assert prompts.behind('practices') is None  # the shipped text the edit was made over
    assert prompts.shipped('practices', 'xml', 'B').version_id == edited.version_id  # the edit is still served
    behind = prompts.behind('practices')
    assert behind is not None and (behind.number, behind.text) == (2, 'B') and behind.seen
    prompts.shipped('practices', 'xml', 'B')
    assert prompts.behind('practices') == behind  # nothing written again
    prompts.shipped('practices', 'xml', 'A')
    assert prompts.behind('practices') is None
    prompts.shipped('practices', 'xml', 'C')
    merged = prompts.save_prompt('practices', 'C, edited')
    assert prompts.behind('practices') is None and prompts.prompt_version('practices') == merged
    assert prompts.behind('nothing') is None


@pytest.mark.req('STORE-029')
def test_a_prompt_store_at_layout_2_is_upgraded_in_place_and_keeps_its_versions(home):
    from metaform.data import prompts
    prompts.add_prompt('practices', 'markdown', 'one')
    db = sqlite3.connect(home / 'prompts.sqlite3')
    db.execute('DROP TABLE prompt_shipped')
    db.execute("UPDATE meta SET value='2' WHERE key='schema_version'")
    db.commit()
    db.close()
    assert prompts.prompt_version('practices').text == 'one'
    prompts.shipped('practices', 'markdown', 'shipped')
    db = sqlite3.connect(home / 'prompts.sqlite3')
    try:
        assert db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() == ('7',)
        assert db.execute("SELECT value FROM meta WHERE key='compatible_from'").fetchone() == ('4',)
        assert db.execute('SELECT COUNT(*) FROM prompt_shipped').fetchone() == (1,)
    finally:
        db.close()


@pytest.mark.req('CTX-082')
@pytest.mark.parametrize(('old_name', 'new_name'), [
    ('dispatch:work', 'prompt.dispatch:work'),
])
def test_legacy_copy_renames_preserve_all_history_and_layer_uses(home, tmp_path, old_name, new_name):
    """Upgrade an isolated legacy copy before exposing canonical serving to a newer client."""
    from metaform.data import prompts
    home.mkdir(parents=True, exist_ok=True)
    legacy = tmp_path / 'legacy.sqlite3'
    with sqlite3.connect(legacy) as db:
        db.executescript(prompts.PROMPT_SCHEMA)
        db.executemany('INSERT INTO meta VALUES (?,?)', [('schema_version', '4'), ('compatible_from', '2')])
        db.execute("INSERT INTO prompts VALUES ('identity',?,'xml','created')", (old_name,))
        db.executemany('INSERT INTO prompt_versions VALUES (?,?,?,?,?,?,?)', [
            ('shipped', 'identity', 1, None, 'Shipped.', 'shipped', 'first'),
            ('override', 'identity', 2, 'shipped', 'My override.', 'edited', 'second')])
        db.execute("INSERT INTO prompt_uses VALUES ('project','base','layer','override')")
        db.execute("INSERT INTO prompt_shipped VALUES ('override','New shipped.','seen')")
    with sqlite3.connect(legacy) as source, sqlite3.connect(home / 'prompts.sqlite3') as target:
        source.backup(target)
    selected = prompts.prompt_version(new_name)
    assert (selected.prompt_id, selected.version_id, selected.text) == ('identity', 'override', 'My override.')
    assert [one.version_id for one in prompts.prompt_versions(selected.name)] == ['override', 'shipped']
    assert prompts.layers_by_prompt_version('override')[0].layer_id == 'layer'
    assert prompts.behind(selected.name).text == 'New shipped.'
    assert prompts.prompt_version(selected.name).version_id == 'override'
    with sqlite3.connect(home / 'prompts.sqlite3') as db:
        assert dict(db.execute('SELECT * FROM meta')) == {
            'schema_version': '7', 'compatible_from': '4', 'prompt_compatibility': '7'}
    with sqlite3.connect(legacy) as db:
        assert db.execute('SELECT name FROM prompts').fetchone()[0] == old_name


@pytest.mark.req('CTX-082')
def test_prompt_address_conflict_preserves_both_histories_and_upgrades_other_names(home):
    from metaform.data import prompts
    home.mkdir(parents=True, exist_ok=True)
    path = home / 'prompts.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript(prompts.PROMPT_SCHEMA)
        db.executemany('INSERT INTO meta VALUES (?,?)', [('schema_version', '4'), ('compatible_from', '2')])
        for number, name in enumerate(('dispatch:work', 'prompt.dispatch:work', 'memory:orient')):
            db.execute('INSERT INTO prompts VALUES (?,?,?,?)', (str(number), name, 'text', 'created'))
            db.execute('INSERT INTO prompt_versions VALUES (?,?,?,?,?,?,?)',
                       (f'version-{number}', str(number), 1, None, f'body-{number}', 'shipped', 'created'))
    assert prompts.prompt_version('prompt.dispatch:work').text == 'body-1'
    assert prompts.prompt_version('dispatch:work').text == 'body-1'
    assert {v.version_id for v in prompts.prompt_versions('dispatch:work')} == {'version-0', 'version-1'}
    assert prompts.prompt_version('0').text == 'body-1'
    assert prompts.prompt_version('prompt.memory:orient').text == 'body-2'
    with sqlite3.connect(path) as db:
        assert [r[0] for r in db.execute('SELECT name FROM prompt_records ORDER BY name')] == [
            'prompt.dispatch:work', 'prompt.memory:orient']
        assert db.execute('SELECT COUNT(*) FROM prompt_versions').fetchone()[0] == 3
        assert dict(db.execute('SELECT * FROM meta')) == {
            'schema_version': '7', 'compatible_from': '4', 'prompt_compatibility': '7'}
    assert prompts.prompt_version('prompt.dispatch:work').version_id == 'version-1'


@pytest.mark.req('CTX-082')
def test_duplicate_names_keep_newest_override_and_roles_resolve(home, project_folder):
    from metaform.data import prompts
    from metaform.module import resolve_agent_role
    home.mkdir(parents=True, exist_ok=True)
    path = home / 'prompts.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript(prompts.PROMPT_SCHEMA)
        db.executemany('INSERT INTO meta VALUES (?,?)', [('schema_version', '6'), ('compatible_from', '6')])
        for identity, name in [('old', 'orchestration:common'), ('new', 'prompt.orchestration:common')]:
            db.execute('INSERT INTO prompts VALUES (?,?,?,?)', (identity, name, 'text', 'created'))
        db.executemany('INSERT INTO prompt_versions VALUES (?,?,?,?,?,?,?)', [
            ('new-first', 'new', 1, None, 'Canonical first.', 'shipped', '2026-10-19T01:00:00Z'),
            ('old-first', 'old', 1, None, 'Legacy first.', 'shipped', '2026-10-19T02:00:00Z'),
            ('old-latest', 'old', 2, 'old-first', 'Latest selected instructions.', 'edited', '2026-10-20T01:00:00Z')])
        db.execute("INSERT INTO prompt_uses VALUES ('project','base','layer','old-latest')")
    for name in ('orchestration:common', 'prompt.orchestration:common', 'old'):
        selected = prompts.prompt_version(name)
        assert selected.version_id == 'old-latest'
        assert selected.text == 'Latest selected instructions.'
        assert selected.name == 'prompt.orchestration:common'
    versions = prompts.prompt_versions('orchestration:common')
    assert [one.version_id for one in versions] == ['old-latest', 'old-first', 'new-first']
    assert versions[0].parent_id == 'old-first'
    assert prompts.layers_by_prompt_version('old-latest')[0].layer_id == 'layer'
    resolved = resolve_agent_role(project_folder, 'functionality')
    assert not resolved['problems'], resolved
    assert resolved['components'][0]['text'] == 'Latest selected instructions.'
    # Legacy write callers also use the canonical identity and cannot split histories again.
    written = prompts.save_prompt('orchestration:common', 'Later override.')
    assert prompts.prompt_version('prompt.orchestration:common').version_id == written.version_id
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM prompt_records WHERE name='orchestration:common'").fetchone()[0] == 0


def test_already_loaded_legacy_sql_reads_and_writes_canonical_history(home):
    from metaform import sqlite
    from metaform.data import prompts
    first = prompts.shipped('prompt.memory:instructions', 'text', 'Canonical instructions.')
    path = home / 'prompts.sqlite3'
    # A process at layout 4 retains its exact old SQL after the new process upgrades the store.
    with sqlite.opened(path, '', write=True, version='4', compatible='2') as db:
        identity = db.execute('SELECT prompt_id FROM prompts WHERE name=?', ('memory:instructions',)).fetchone()[0]
        assert identity == first.prompt_id
        selected = db.execute('SELECT v.text FROM prompt_versions v JOIN prompts p ON p.prompt_id=v.prompt_id '
                              'WHERE v.prompt_id=? ORDER BY v.number DESC LIMIT 1', (identity,)).fetchone()
        assert selected[0] == 'Canonical instructions.'
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO prompt_versions VALUES (?,?,?,?,?,?,?)',
                   ('old-process-version', identity, 2, first.version_id, 'Old process edit.', 'edited', 'later'))
        db.execute("INSERT INTO prompts VALUES ('old-created','dispatch:legacy_new','text','later')")
        db.execute("INSERT INTO prompt_versions VALUES ('old-created-v1','old-created',1,NULL,'Old new prompt.',"
                   "'shipped','later')")
        db.execute('COMMIT')
    assert prompts.prompt_version('memory:instructions').text == 'Old process edit.'
    assert prompts.prompt_version('prompt.memory:instructions').version_id == 'old-process-version'
    assert prompts.prompt_version('prompt.dispatch:legacy_new').text == 'Old new prompt.'
