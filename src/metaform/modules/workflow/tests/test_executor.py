"""Call scopes and nonce handoffs survive process boundaries, BASE-051."""
import json
import subprocess
import sys

import pytest

from metaform import nonce
from metaform.data.records import plain
from metaform.modules.workflow import executor
from metaform.modules.workflow.binding import Logic
from metaform.modules.workflow.element import ElementValue

pytestmark = [pytest.mark.req('BASE-051'), pytest.mark.req('MAP-056'), pytest.mark.kind('fixture')]

SCRIPT = '@STATE_INIT:\n {target} := PARAM\n@CONSTRAINT:\n'


def lookup(address, name):
    return Logic('logic', name, name, SCRIPT), ElementValue({'address': address})


def begin():
    return executor.start('({ok}, {issues}) := workflow.quality.code.improve(target=this)',
                          {'secret': 'caller history'}, ElementValue({'address': 'code.timer'}), lookup,
                          {'project': 'proj', 'folder': '/tmp', 'metaform': None, 'layers': []})


def test_same_agent_nested_calls_restore_values_and_callee_this(home):
    word = begin()
    first = executor.view(word)
    assert first['this'].address == 'workflow.quality.code'
    assert first['arguments']['target'].address == 'code.timer'
    variables = {**first['variables'], 'attempt': 2}
    executor.call(word, '({ok}, {issues}) := workflow.review.code.review(target={target})', variables, lookup)
    child = executor.view(word)
    assert child['this'].address == 'workflow.review.code'
    assert 'attempt' not in child['variables']
    resumed = executor.complete(word, 'RETURN (TRUE, [])', {})
    assert resumed['variables']['attempt'] == 2 and resumed['variables']['ok'] is True
    result = executor.complete(word, 'RETURN ({ok}, {issues})', resumed['variables'])
    assert result == {'value': (True, []), 'variables': {'secret': 'caller history', 'ok': True, 'issues': []}}
    assert not nonce.read(word).open


def test_fresh_handoff_redeems_in_another_process_with_only_callee_context(home):
    parent = begin()
    child = executor.call(parent, '({ok}, {issues}) := workflow.review.code.review(target={target})',
                          {**executor.view(parent)['variables'], 'private': 'caller only'}, lookup, fresh=True)
    script = 'import json; from metaform.data.records import plain; ' \
             'from metaform.modules.workflow.executor import view; print(json.dumps(plain(view(__import__("sys").argv[1]))))'
    result = subprocess.run([sys.executable, '-c', script, child], capture_output=True, text=True, check=True)
    visible = json.loads(result.stdout)
    assert 'private' not in visible['variables'] and 'secret' not in result.stdout
    assert visible['arguments']['target']['address'] == 'code.timer'
    assert visible['logic']['content'] == SCRIPT
    assert executor.view(parent)['state'] == 'waiting'
    with pytest.raises(Exception, match='waiting'):
        executor.complete(parent, 'RETURN TRUE', {})
    resumed = executor.complete(child, 'RETURN (TRUE, [])', {})
    assert resumed == {'resume': parent}
    assert executor.view(parent)['variables']['private'] == 'caller only'
    assert not nonce.read(child).open
    assert executor.view(parent)['state'] == 'running'


def test_error_propagates_unchanged_to_caller_and_then_orchestrator(home):
    parent = begin()
    executor.call(parent, '{fixed} := workflow.quality.code.fix(target={target})',
                  executor.view(parent)['variables'], lookup)
    resumed = executor.fail(parent, 'SourceUnreadable', 'src/timer.py')
    assert resumed['error'] == {'name': 'SourceUnreadable', 'message': 'src/timer.py'}
    assert 'fixed' not in resumed['variables']
    assert executor.fail(parent, name='SourceUnreadable', message='src/timer.py') == {
        'error': {'name': 'SourceUnreadable', 'message': 'src/timer.py'}}


def test_parallel_waits_for_every_branch_and_preserves_every_error(home):
    parent = begin()
    words = executor.parallel(parent, ['{a} := workflow.review.code.review(target={target})',
                                      '{b} := workflow.review.code.review(target={target})'],
                              executor.view(parent)['variables'], lookup)
    assert executor.fail(words[0], 'FirstFailed', 'first') == {'caller': parent, 'state': 'waiting'}
    resumed = executor.complete(words[1], 'RETURN TRUE', {})
    assert resumed == {'resume': parent}
    resumed = executor.view(parent)
    assert resumed['variables']['b'] is True
    assert resumed['branches'] == [{'nonce': words[0], 'error': {'name': 'FirstFailed', 'message': 'first'}},
                                  {'nonce': words[1], 'value': True}]
    assert not any(nonce.read(one).open for one in words)


def test_failed_return_binding_keeps_child_available_to_correct(home):
    parent = begin()
    executor.call(parent, '({ok}, {issues}) := workflow.review.code.review(target={target})',
                  executor.view(parent)['variables'], lookup)
    with pytest.raises(ValueError):
        executor.complete(parent, 'RETURN (TRUE,)', {})
    assert executor.view(parent)['logic']['name'] == 'review'
    assert executor.complete(parent, 'RETURN (TRUE, [])', {})['variables']['ok'] is True


def test_tuple_values_and_read_only_element_views_roundtrip(home):
    original = {'element': ElementValue({'address': 'code.timer', 'refs': {'path': ['timer.py']}}),
                'tuple': ('one', ['two'])}
    restored = executor.unpack(json.loads(json.dumps(executor.pack(original))))
    assert restored['element'].refs['path'] == ['timer.py']
    assert isinstance(restored['tuple'], tuple)
    assert plain(restored) == plain(original)


def test_parallel_bad_return_keeps_branch_open_for_correction(home):
    parent = begin()
    words = executor.parallel(parent, ['({a}, {b}) := workflow.review.code.review(target={target})',
                                      '{c} := workflow.review.code.review(target={target})'],
                              executor.view(parent)['variables'], lookup)
    with pytest.raises(ValueError):
        executor.complete(words[0], 'RETURN (TRUE,)', {})
    assert nonce.read(words[0]).open
    executor.complete(words[0], 'RETURN (TRUE, FALSE)', {})
    assert executor.complete(words[1], 'RETURN TRUE', {}) == {'resume': parent}
    assert executor.view(parent)['variables']['b'] is False


def test_caller_can_run_its_catch_handler_and_use_its_return(home):
    parent = begin()
    executor.call(parent, '{fixed} := workflow.quality.code.fix(target={target})',
                  executor.view(parent)['variables'], lookup)
    failed = executor.fail(parent, 'FixFailed', 'The issue remains.')
    assert failed['error']['name'] == 'FixFailed'
    executor.call(parent, '{fixed} := workflow.quality.code.diagnose(target={target})',
                  failed['variables'], lookup)
    recovered = executor.complete(parent, 'RETURN "diagnosed cause"', {})
    assert recovered['variables']['fixed'] == 'diagnosed cause'
    assert 'error' not in recovered
