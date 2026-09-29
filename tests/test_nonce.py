"""The nonce service: a module requests a nonce, and an agent reaches its work by running metaform <nonce>, BASE-050."""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('BASE-050')]

STEPS = '''
    from metaform import nonce
    from metaform.module import Module, Noun, Verb
    SUPPORTED_OS = ('linux', 'macos', 'windows')
    PROMPTS = ('Write the plan.', 'Review the plan.')

    def begin(ctx):
        return 'metaform ' + nonce.request('steps', 'prompt', {'at': 0})

    def prompt(ctx):
        return PROMPTS[nonce.current().value['at']]

    def next_(ctx):
        held = nonce.current()
        if held.value['at'] + 1 == len(PROMPTS):
            nonce.close(held.nonce)
            return 'done'
        nonce.update(held.nonce, value={'at': held.value['at'] + 1})
        return PROMPTS[held.value['at'] + 1]

    def complete(ctx):
        held = nonce.current()
        nonce.close(held.nonce)
        return 'Give this to the main agent: metaform ' + nonce.request('steps', 'prompt', {'at': 1})

    def say(ctx):
        return str(ctx.nouns['word']) + ' at ' + str(nonce.current().value['at'])

    MODULE = Module(id='steps', summary='Two steps.', purpose='Two steps. Details: metaform help steps.',
                    verbs=(Verb('begin', begin, 'Begin.'), Verb('prompt', prompt, 'The prompt of the step.'),
                           Verb('next', next_, 'The next step.'), Verb('complete', complete, 'Hand the work on.'),
                           Verb('say', say, 'Say a word.', nouns=(Noun('word', 'The word.'),))))
'''


@pytest.fixture
def steps(run, tmp_path, user_module):
    user_module('steps', STEPS)
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    return folder


def issued(run, folder):
    said = run('steps', 'begin', cwd=folder).stdout.split()
    assert said[0] == 'metaform' and len(said) == 2
    return said[1]


def test_a_module_requests_a_nonce_and_its_record_names_the_module_and_its_function(run, steps):
    from metaform import nonce
    held = nonce.read(issued(run, steps))
    assert (held.module, held.function, held.value, held.open) == ('steps', 'prompt', {'at': 0}, True)
    assert issued(run, steps) != held.nonce


def test_the_nonce_alone_gives_the_agent_what_the_modules_function_returns(run, steps):
    assert run(issued(run, steps), cwd=steps).stdout.strip() == 'Write the plan.'


def test_help_on_a_nonce_lists_the_commands_of_its_module_and_no_others(run, steps):
    shown = run(issued(run, steps), 'help', cwd=steps).stdout
    for command in ('prompt', 'next', 'complete', 'say'):
        assert command in shown
    for other in ('intake', 'map', 'config', 'enable'):
        assert other not in shown.split()


def test_a_command_run_through_a_nonce_reaches_the_module_with_what_the_chassis_holds(run, steps):
    nonce = issued(run, steps)
    assert run(nonce, 'say', 'hello', cwd=steps).stdout.strip() == 'hello at 0'
    assert run(nonce, 'next', cwd=steps).stdout.strip() == 'Review the plan.'
    assert run(nonce, cwd=steps).stdout.strip() == 'Review the plan.'       # the update changed what is sent
    assert run(nonce, 'say', 'hello', cwd=steps).stdout.strip() == 'hello at 1'


def test_a_closed_nonce_runs_nothing_and_says_it_is_closed(run, steps):
    nonce = issued(run, steps)
    run(nonce, 'next', cwd=steps)
    assert run(nonce, 'next', cwd=steps).stdout.strip() == 'done'
    for rest in ((), ('next',), ('help',)):
        refused = run(nonce, *rest, cwd=steps, ok=False)
        assert refused.returncode == 2 and 'closed' in refused.stderr and refused.stdout == ''


def test_a_module_closes_a_nonce_and_hands_on_a_new_one(run, steps):
    first = issued(run, steps)
    second = run(first, 'complete', cwd=steps).stdout.split()[-1]
    assert second != first and run(second, cwd=steps).stdout.strip() == 'Review the plan.'
    assert run(first, cwd=steps, ok=False).returncode == 2


def test_a_command_the_module_does_not_have_is_named_with_the_way_to_list_them(run, steps):
    nonce = issued(run, steps)
    refused = run(nonce, 'fly', cwd=steps, ok=False)
    assert refused.returncode == 2 and 'fly' in refused.stderr and f'metaform {nonce} help' in refused.stderr


def test_a_nonce_never_has_the_name_of_a_command_or_a_module(run, steps):
    from metaform import loader, nonce
    from metaform.cli import VERBS
    names = set(VERBS) | {found.id for found in loader.discover()}
    assert not {nonce.request('steps', 'prompt') for _ in range(50)} & names


def test_a_home_made_before_nonces_existed_is_given_the_table_on_the_first_request(run, steps, home):
    import sqlite3

    from metaform import home as metaform_home
    from metaform import nonce
    db = sqlite3.connect(metaform_home.base_path())
    db.execute('DROP TABLE nonces')
    db.commit()
    db.close()
    assert nonce.read('0a1b2c3d') is None
    assert run('0a1b2c3d', cwd=steps, ok=False).returncode == 2       # read as a module that is not there
    assert run(issued(run, steps), cwd=steps).stdout.strip() == 'Write the plan.'
