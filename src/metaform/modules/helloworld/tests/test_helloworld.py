"""helloworld exercises each chassis feature once; each test fails if the chassis drops that feature, BASE-019."""
from __future__ import annotations


import pytest

pytestmark = pytest.mark.kind('fixture')


@pytest.fixture
def hello(run, tmp_path):
    """helloworld enabled, in a registered project folder."""
    run('enable', 'helloworld')
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    return folder


@pytest.mark.req('BASE-019')
@pytest.mark.req('CLI-012')
@pytest.mark.req('CLI-011')
def test_greet_takes_a_noun_and_a_switch_that_is_a_setting(run, hello):
    assert run('helloworld', 'greet', 'world', cwd=hello).stdout.strip() == 'hello, world'
    assert run('helloworld', 'greet', 'world', '--loud', cwd=hello).stdout.strip() == 'HELLO, WORLD!'
    run('set', '--loud', cwd=hello)
    assert run('helloworld', 'greet', 'world', cwd=hello).stdout.strip() == 'HELLO, WORLD!'
    assert run('helloworld', 'greet', 'world', '--no-loud', cwd=hello).stdout.strip() == 'hello, world'
    run('set', '--greeting', 'hi', cwd=hello)
    run('unset', '--loud', cwd=hello)
    assert run('helloworld', 'greet', 'you', cwd=hello).stdout.strip() == 'hi, you'


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-009')
def test_wait_is_an_async_verb(run, hello):
    assert run('helloworld', 'wait', '0', cwd=hello).stdout.strip() == 'waited 0 s'


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
                        subscriptions=(Subscription('helloworld.greeted', saw),))
    ''')
    run('helloworld', 'greet', 'ada', cwd=hello)
    run('helloworld', 'greet', 'bob', cwd=hello)
    assert run('helloworld', 'history', cwd=hello).stdout.split() == ['ada', 'bob']
    from metaform.data import Store
    layers = {layer.name: layer for layer in Store('proj').layers(limit=0).results}
    assert layers['helloworld.greetings'].module == 'helloworld'
    assert [item.value for item in Store('proj').layer_items('witnessed').results] == ['ada', 'bob']


@pytest.mark.req('BASE-019')
@pytest.mark.req('CLI-019')
def test_the_favorite_setting_takes_its_choices_from_the_modules_data(run, hello, tmp_path):
    refused = run('set', '--favorite', 'zed', cwd=hello, ok=False)
    assert refused.returncode == 2
    run('helloworld', 'greet', 'zed', cwd=hello)
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
    run('helloworld', 'greet', 'ada', cwd=hello)
    refused = run('helloworld', 'forget', cwd=hello, ok=False)
    assert refused.stderr.splitlines()[-1] == 'Next: If you are sure: metaform helloworld forget --confirm'
    assert run('helloworld', 'history', cwd=hello).stdout.split() == ['ada']
    run('helloworld', 'forget', '--confirm', cwd=hello)
    assert run('helloworld', 'history', cwd=hello).stdout.startswith('No greetings yet.')


@pytest.mark.req('STORE-023')
@pytest.mark.req('CLI-020')
def test_a_verb_that_needs_a_project_names_the_way_to_register_one(run, tmp_path):
    run('enable', 'helloworld')
    folder = tmp_path / 'nowhere'
    folder.mkdir()
    refused = run('helloworld', 'greet', 'ada', cwd=folder, ok=False)
    assert refused.returncode == 2
    assert refused.stderr.splitlines() == ['Error: No project for this folder.',
                                           'Next: metaform add project <id> <path>']


@pytest.mark.req('STORE-022')
@pytest.mark.req('BASE-002')
def test_every_verb_keeps_its_data_in_the_store(run, hello, home):
    run('helloworld', 'greet', 'ada', cwd=hello)
    run('helloworld', 'wait', '0', cwd=hello)
    run('helloworld', 'history', cwd=hello)
    run('helloworld', 'forget', '--confirm', cwd=hello)
    files = {path.relative_to(home).parts for path in home.rglob('*') if path.is_file()}
    allowed = [lambda parts: parts[0].startswith('metaform.sqlite3'),
               lambda parts: parts[0] == 'projects' and parts[-1].startswith('store.sqlite3')]
    assert [parts for parts in files if not any(rule(parts) for rule in allowed)] == []


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-035')
def test_the_status_hook_adds_a_line(run, hello):
    run('helloworld', 'greet', 'ada', cwd=hello)
    assert 'Helloworld: 1 greeted' in run(cwd=hello).stdout.splitlines()


@pytest.mark.req('BASE-019')
@pytest.mark.req('BASE-016')
def test_beep_runs_only_on_its_own_system(run, hello):
    import platform
    on_windows = platform.system() == 'Windows'
    assert ('helloworld beep' in run('help', 'commands', cwd=hello).stdout) == on_windows
    if not on_windows:
        refused = run('helloworld', 'beep', cwd=hello, ok=False)
        assert refused.stderr.splitlines() == ['Error: helloworld beep runs on windows.', 'Next: metaform help helloworld']
