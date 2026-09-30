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

    def demo(ctx):
        held = nonce.reached()
        if held is None:
            return 'Please run metaform ' + nonce.request('steps', 'demo', {'runs': 0})
        nonce.update(held.nonce, value={'runs': held.value['runs'] + 1})
        return held.nonce + ' run ' + str(nonce.reached().value['runs'])

    def finish(ctx):
        nonce.close(nonce.reached().nonce)
        return 'open' if nonce.reached().open else 'closed'

    MODULE = Module(id='steps', summary='Two steps.', purpose='Two steps. Details: metaform help steps.',
                    verbs=(Verb('begin', begin, 'Begin.'), Verb('prompt', prompt, 'The prompt of the step.'),
                           Verb('next', next_, 'The next step.'), Verb('complete', complete, 'Hand the work on.'),
                           Verb('say', say, 'Say a word.', nouns=(Noun('word', 'The word.'),)),
                           Verb('demo', demo, 'Begin, or run through the nonce.'),
                           Verb('finish', finish, 'Close the nonce.')))
'''

UNKNOWN = 'Error: Invalid or Unknown Nonce\n'


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


def test_a_nonce_is_seven_digits_and_never_begins_with_zero(run, steps):
    import re

    from metaform import nonce
    drawn = [issued(run, steps)] + [nonce.request('steps', 'prompt') for _ in range(200)]
    assert all(re.fullmatch(r'[1-9][0-9]{6}', word) for word in drawn), drawn


def test_a_closed_nonce_runs_nothing_and_prints_exactly_invalid_or_unknown_nonce(run, steps):
    nonce = issued(run, steps)
    run(nonce, 'next', cwd=steps)
    assert run(nonce, 'next', cwd=steps).stdout.strip() == 'done'
    for rest in ((), ('next',), ('help',)):
        refused = run(nonce, *rest, cwd=steps, ok=False)
        assert (refused.returncode, refused.stdout, refused.stderr) == (2, '', UNKNOWN)


def test_a_nonce_that_was_never_issued_prints_exactly_invalid_or_unknown_nonce(run, steps):
    from metaform import nonce
    issued(run, steps)
    never = next(word for word in map(str, range(1000000, 1000100)) if nonce.read(word) is None)
    for rest in ((), ('next',), ('help',)):
        refused = run(never, *rest, cwd=steps, ok=False)
        assert (refused.returncode, refused.stdout, refused.stderr) == (2, '', UNKNOWN)


def test_a_closed_nonce_is_kept_so_its_number_is_never_issued_again(run, steps, monkeypatch):
    from metaform import nonce
    closed, still_open = issued(run, steps), issued(run, steps)
    nonce.close(closed)
    assert nonce.read(closed) is not None and not nonce.read(closed).open
    fresh = next(word for word in map(str, range(1000000, 1000100)) if nonce.read(word) is None)
    monkeypatch.setattr(nonce, '_draw', iter([closed, still_open, fresh]).__next__)
    assert nonce.request('steps', 'prompt') == fresh


def test_reached_is_none_when_the_command_did_not_come_through_a_nonce(run, steps):
    said = run('steps', 'demo', cwd=steps).stdout.split()
    assert said[:3] == ['Please', 'run', 'metaform'] and len(said) == 4


def test_reached_is_the_nonce_the_command_came_through_so_one_verb_is_also_its_function(run, steps):
    word = run('steps', 'demo', cwd=steps).stdout.split()[-1]
    assert run(word, cwd=steps).stdout.strip() == f'{word} run 1'
    assert run(word, cwd=steps).stdout.strip() == f'{word} run 2'       # the chassis holds the update
    assert run(word, 'demo', cwd=steps).stdout.strip() == f'{word} run 3'


def test_reached_follows_a_close_in_the_same_command(run, steps):
    word = run('steps', 'demo', cwd=steps).stdout.split()[-1]
    assert run(word, 'finish', cwd=steps).stdout.strip() == 'closed'
    assert run(word, cwd=steps, ok=False).stderr == UNKNOWN


def test_a_module_closes_a_nonce_and_hands_on_a_new_one(run, steps):
    first = issued(run, steps)
    second = run(first, 'complete', cwd=steps).stdout.split()[-1]
    assert second != first and run(second, cwd=steps).stdout.strip() == 'Review the plan.'
    assert run(first, cwd=steps, ok=False).returncode == 2


def test_a_command_the_module_does_not_have_is_named_with_the_way_to_list_them(run, steps):
    nonce = issued(run, steps)
    refused = run(nonce, 'fly', cwd=steps, ok=False)
    assert refused.returncode == 2 and 'fly' in refused.stderr and f'metaform {nonce} help' in refused.stderr


WORDS = '''
    from metaform import nonce
    from metaform.module import Module, Noun, Verb
    SUPPORTED_OS = ('linux', 'macos', 'windows')

    def hear(ctx):
        held = nonce.reached()
        if held is None:
            return 'metaform ' + nonce.request('words', 'hear')
        return held.nonce + ' heard ' + ' '.join(ctx.nouns.get('word', ()))

    def other(ctx):
        return 'other ran'

    MODULE = Module(id='words', summary='Words.', purpose='Hears words. Details: metaform help words.',
                    verbs=(Verb('hear', hear, 'Begin, or hear the words after the nonce.',
                                nouns=(Noun('word', 'A word after the nonce.', required=False, many=True),)),
                           Verb('other', other, 'Another command.')))
'''


def test_the_words_after_a_nonce_that_name_none_of_its_modules_commands_reach_its_function(run, tmp_path,
                                                                                          user_module):
    user_module('words', WORDS)
    folder = tmp_path / 'proj'
    folder.mkdir()
    run('add', 'project', 'proj', str(folder))
    word = run('words', 'hear', cwd=folder).stdout.split()[-1]
    assert run(word, 'next', cwd=folder).stdout == f'{word} heard next'
    assert run(word, 'next', 'step', cwd=folder).stdout == f'{word} heard next step'
    assert run(word, cwd=folder).stdout == f'{word} heard '
    assert run(word, 'other', cwd=folder).stdout == 'other ran'   # a word that names one of its commands runs it


def test_a_nonce_never_has_the_name_of_a_command_or_a_module(run, steps):
    from metaform import loader, nonce
    from metaform.cli import VERBS
    names = set(VERBS) | {found.id for found in loader.discover()}
    assert not {nonce.request('steps', 'prompt') for _ in range(50)} & names


def test_a_home_made_before_nonces_existed_is_given_the_table_on_the_first_request(run, steps, home):
    import sqlite3

    from metaform import home as metaform_home
    from metaform import nonce
    metaform_home.set_meta('made', 'before nonces')  # the chassis database exists, as it did then
    db = sqlite3.connect(metaform_home.base_path())
    db.execute('DROP TABLE nonces')
    db.commit()
    db.close()
    assert nonce.read('1000000') is None
    assert run('1000000', cwd=steps, ok=False).stderr == UNKNOWN
    assert run(issued(run, steps), cwd=steps).stdout.strip() == 'Write the plan.'
