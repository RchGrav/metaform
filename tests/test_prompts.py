"""Prompts: versioned records in the home's prompt store, and the version each layer was made from, STORE-044."""
from __future__ import annotations

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
    assert [(use.project_id, use.metaform_id, use.layer_id) for use in prompts.layers_by_prompt_version(
        third.version_id)] == [('proj', 'metaform-1', 'layer-1')]
    assert prompts.use_of('proj', 'metaform-1', 'layer-1').number == 3
    assert prompts.use_of('proj', 'metaform-1', 'layer-2') is None


@pytest.mark.req('STORE-044')
def test_a_shipped_prompt_flows_in_until_someone_saves_an_edit(home):
    from metaform.data import prompts
    first = prompts.shipped('canonical-intake', 'xml', '<process>A</process>')
    assert (first.number, first.origin) == (1, 'shipped')
    assert prompts.shipped('canonical-intake', 'xml', '<process>A</process>').version_id == first.version_id
    second = prompts.shipped('canonical-intake', 'xml', '<process>B</process>')
    assert (second.number, second.origin, second.parent_id) == (2, 'shipped', first.version_id)
    edited = prompts.add_prompt_version('canonical-intake', '<process>B, edited</process>', 2)
    kept = prompts.shipped('canonical-intake', 'xml', '<process>C</process>')
    assert kept.version_id == edited.version_id and kept.text == '<process>B, edited</process>'
    assert [version.number for version in prompts.prompt_versions('canonical-intake')] == [3, 2, 1]


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
