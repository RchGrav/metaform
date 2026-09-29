"""hello exercises each chassis feature once; each test fails if the chassis drops that feature, BASE-019."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def hello(run, tmp_path):
    """hello enabled, in a registered project folder."""
    run('enable', 'hello')
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    return folder


@pytest.mark.req('BASE-019')
@pytest.mark.req('CLI-012')
@pytest.mark.req('CLI-011')
def test_greet_takes_a_noun_and_a_switch_that_is_a_setting(run, hello):
    assert run('hello', 'greet', 'world', cwd=hello).stdout.strip() == 'hello, world'
    assert run('hello', 'greet', 'world', '--loud', cwd=hello).stdout.strip() == 'HELLO, WORLD!'
    run('set', '--loud', cwd=hello)
    assert run('hello', 'greet', 'world', cwd=hello).stdout.strip() == 'HELLO, WORLD!'
    assert run('hello', 'greet', 'world', '--no-loud', cwd=hello).stdout.strip() == 'hello, world'
    run('set', '--greeting', 'hi', cwd=hello)
    run('unset', '--loud', cwd=hello)
    assert run('hello', 'greet', 'you', cwd=hello).stdout.strip() == 'hi, you'


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-009')
def test_wait_is_an_async_verb(run, hello):
    assert run('hello', 'wait', '0', cwd=hello).stdout.strip() == 'waited 0 s'


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-010')
@pytest.mark.req('STORE-022')
def test_the_greeted_event_is_recorded_as_a_layer(run, hello, home, user_module):
    user_module('witness', '''
        from metaform.data import Node
        from metaform.module import Module, Subscription
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        def saw(payload, ctx):
            store = ctx.require_store()
            with store.atomic():
                store.layer('witnessed', 'witness', 'Greetings seen.', mutable=True, hideable=True,
                            provenance={'module': 'witness'})
                store.add_element('witnessed', 'code.witness')
                store.add_item('witnessed', Node('element', 'code.witness'), payload['name'])
        MODULE = Module(id='witness', summary='x', purpose='Witnesses. Details: metaform help witness.',
                        subscriptions=(Subscription('hello.greeted', saw),))
    ''')
    run('hello', 'greet', 'ada', cwd=hello)
    run('hello', 'greet', 'bob', cwd=hello)
    assert run('hello', 'history', cwd=hello).stdout.split() == ['ada', 'bob']
    from metaform.data import Store
    layers = {layer.name: layer for layer in Store('proj').layers(limit=0).results}
    assert layers['hello.greetings'].module == 'hello'
    assert [item.value for item in Store('proj').layer_items('witnessed').results] == ['ada', 'bob']


@pytest.mark.req('BASE-019')
@pytest.mark.req('CLI-019')
def test_the_favorite_setting_takes_its_choices_from_the_modules_data(run, hello, tmp_path):
    refused = run('set', '--favorite', 'zed', cwd=hello, ok=False)
    assert refused.returncode == 2
    run('hello', 'greet', 'zed', cwd=hello)
    run('set', '--favorite', 'zed', cwd=hello)
    elsewhere = tmp_path / 'nowhere'
    elsewhere.mkdir()
    outside = run('set', '--favorite', 'zed', cwd=elsewhere, ok=False)
    assert outside.stderr.splitlines() == [
        'Error: --favorite has no choices here: this folder is not in a registered project.',
        'Next: metaform add project <id> <path>']


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-013')
def test_forget_needs_confirm(run, hello):
    run('hello', 'greet', 'ada', cwd=hello)
    refused = run('hello', 'forget', cwd=hello, ok=False)
    assert refused.stderr.splitlines()[-1] == 'Next: If you are sure: metaform hello forget --confirm'
    assert run('hello', 'history', cwd=hello).stdout.split() == ['ada']
    run('hello', 'forget', '--confirm', cwd=hello)
    assert run('hello', 'history', cwd=hello).stdout.startswith('No greetings yet.')


@pytest.mark.req('STORE-023')
@pytest.mark.req('CLI-020')
def test_a_verb_that_needs_a_project_names_the_way_to_register_one(run, tmp_path):
    run('enable', 'hello')
    folder = tmp_path / 'nowhere'
    folder.mkdir()
    refused = run('hello', 'greet', 'ada', cwd=folder, ok=False)
    assert refused.returncode == 2
    assert refused.stderr.splitlines() == ['Error: No project for this folder.',
                                           'Next: metaform add project <id> <path>']


@pytest.mark.req('STORE-022')
@pytest.mark.req('BASE-002')
def test_every_verb_keeps_its_data_in_the_store(run, hello, home):
    run('hello', 'greet', 'ada', cwd=hello)
    run('hello', 'wait', '0', cwd=hello)
    run('hello', 'history', cwd=hello)
    run('hello', 'forget', '--confirm', cwd=hello)
    files = {path.relative_to(home).parts for path in home.rglob('*') if path.is_file()}
    allowed = [lambda parts: parts[0].startswith('metaform.sqlite3'),
               lambda parts: parts[0] == 'projects' and parts[-1].startswith('store.sqlite3')]
    assert [parts for parts in files if not any(rule(parts) for rule in allowed)] == []


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-035')
def test_the_status_hook_adds_a_line(run, hello):
    run('hello', 'greet', 'ada', cwd=hello)
    assert 'Hello: 1 greeted' in run(cwd=hello).stdout.splitlines()


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-016')
def test_beep_runs_only_on_its_own_system(run, hello):
    import platform
    on_windows = platform.system() == 'Windows'
    assert ('hello beep' in run('help', 'commands', cwd=hello).stdout) == on_windows
    if not on_windows:
        refused = run('hello', 'beep', cwd=hello, ok=False)
        assert refused.stderr.splitlines() == ['Error: hello beep runs on windows.', 'Next: metaform help hello']


@pytest.mark.req('BASE-019')
@pytest.mark.req('QUAL-016')
@pytest.mark.req('MAP-046')
def test_todo_writes_a_work_record_on_the_modules_own_element_and_done_resolves_it(run, hello):
    """Rich, 2026-09-26: a capability added for a feature gets a demonstration in hello; here a module writes the
    condition of its own element as a work record, apart from the map, and resolves it, MAP-046."""
    from metaform.data import Node, Store
    run('hello', 'greet', 'ada', cwd=hello)
    said = run('hello', 'todo', 'greet in every language', cwd=hello).stdout.strip()
    store = Store('proj')
    records = store.work(node=Node('element', 'code.module.hello')).results
    assert [(row.condition, row.task, row.done) for row in records] == [('tbd', 'greet in every language', None)]
    assert said == f'To do: greet in every language ({records[0].work_id})'
    assert store.element('code.module.hello', raw=True).open_work == ('tbd',)
    assert 'Hello: 1 greeted, 1 to do' in run(cwd=hello).stdout.splitlines()
    run('hello', 'done', records[0].work_id, 'greets in Latin now', cwd=hello)
    finished = store.work(node=Node('element', 'code.module.hello')).results[0]
    assert (finished.resolution, finished.done is not None) == ('greets in Latin now', True)
    assert store.element('code.module.hello', raw=True).open_work == ()
    assert 'Hello: 1 greeted' in run(cwd=hello).stdout.splitlines()


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-050')
def test_a_task_is_handed_out_by_nonce_and_closed_when_it_is_finished(run, hello):
    said = run('hello', 'task', 'ada', cwd=hello).stdout.split()
    assert said[:2] == ['Run:', 'metaform'] and len(said) == 3
    nonce = said[2]
    assert run(nonce, cwd=hello).stdout.strip() == f'Greet ada, then run: metaform {nonce} finish'
    assert 'finish' in run(nonce, 'help', cwd=hello).stdout
    assert run(nonce, 'finish', cwd=hello).stdout.strip() == 'ada is greeted; the task is complete.'
    assert run('hello', 'history', cwd=hello).stdout.split() == ['ada']
    assert run(nonce, cwd=hello, ok=False).returncode == 2
