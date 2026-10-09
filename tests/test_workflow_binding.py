"""Calls keep the caller's element and variables separate from a subroutine's scope."""
from types import SimpleNamespace

import pytest
from storekit import knowledge, small_map

from metaform.data import Node
from metaform.data.records import plain
from metaform.modules.workflow.binding import Logic, prepare, receive, returned
from metaform.modules.workflow.element import element_value

pytestmark = [pytest.mark.req('MAP-056'), pytest.mark.req('MAP-057'), pytest.mark.kind('fixture')]


REVIEW = '''@STATE_INIT:
  {target} := PARAM
  {standard} := PARAM = "default"
  {paths} := PARAM = NULL
  {issues} := []
@CONSTRAINT:
  +> Acceptance: every part of {target} has been checked.
@CONDITION (RESULT):
  ?IF ( {issues} is empty ) -> {ok} := TRUE
@ROUTER:
  EXECUTE_PIPELINE( Review )
@EXECUTE_PIPELINE (Review):
  [STEP 1]: Review {target} against {standard}.
  [STEP 2]: RETURN ( {ok}, {issues} ).
@VERIFY:
  [V1] Was every part checked? NO -> RECURSE Review.
'''


def test_call_passes_element_and_values_without_rewriting_the_script():
    target = SimpleNamespace(address='code.alarm.audible', refs={'path': ['alarm.py']})
    workflow = SimpleNamespace(address='workflow.quality.code')
    logic = Logic('logic', 'stable', 'review', REVIEW)
    resolved = []

    def lookup(address, name):
        resolved.append((address, name))
        return logic, workflow

    caller = {'old': 'kept', 'ok': None}
    frame = prepare('( {ok}, {issues} ) := workflow.quality.code.review('
                    'target=this, paths=this.refs.get("path"), standard=None)', caller, target, lookup)
    assert resolved == [('workflow.quality.code', 'review')]
    assert frame.logic.content == REVIEW
    assert frame.arguments == {'target': target, 'standard': 'default', 'paths': ['alarm.py']}
    assert frame.this is workflow
    assert caller == {'old': 'kept', 'ok': None}
    value = returned('RETURN ( {ok}, {issues} )', {'ok': True, 'issues': []}, frame.this)
    assert receive(frame, value, caller) == {'old': 'kept', 'ok': True, 'issues': []}
    assert caller == {'old': 'kept', 'ok': None}


def test_composed_call_uses_callee_this_and_explicitly_passed_caller_target():
    project = SimpleNamespace(address='code.alarm.audible')
    first = SimpleNamespace(address='workflow.quality.code')
    second = SimpleNamespace(address='workflow.diagnosis.code')
    logic = Logic('logic', 'another', 'diagnose', '@STATE_INIT:\n  {element} := PARAM\n@CONSTRAINT:\n')
    frame = prepare('{cause} := workflow.diagnosis.code.diagnose(element={target})',
                    {'target': project}, first, lambda *_: (logic, second))
    assert frame.arguments['element'] is project
    assert returned('RETURN ( {element}.address, this.address )', frame.arguments, frame.this) == (
        'code.alarm.audible', 'workflow.diagnosis.code')
    assert receive(frame, 'cause', {}) == {'cause': 'cause'}


def test_absent_required_parameter_and_missing_keys_fail_to_caller():
    logic = Logic('logic', 'stable', 'review', REVIEW)
    lookup = lambda *_: (logic, None)
    for call in ('workflow.quality.code.review()', 'workflow.quality.code.review(target=None)'):
        with pytest.raises(TypeError, match='target'):
            prepare(call, {}, None, lookup)
    with pytest.raises(KeyError, match='path'):
        prepare('workflow.quality.code.review(target=this.refs["path"])', {},
                SimpleNamespace(refs={}), lookup)
    with pytest.raises(ValueError):
        receive(prepare('({ok}, {issues}) := workflow.quality.code.review(target="alarm")', {}, None, lookup),
                (True,), {})


def test_keywords_and_literal_defaults_preserve_false_zero_and_placeholder_text():
    content = '@STATE_INIT:\n {SHARED} := [\n axiom-language 1 ]\n {target} := PARAM # required\n' \
              ' {count} := PARAM = 3\n {flag} := PARAM = TRUE\n' \
              ' {label} := PARAM = "literal {target} # stays"\n@CONSTRAINT:\n {outside} := PARAM\n'
    logic = Logic('logic', 'stable', 'review', content)
    frame = prepare('workflow.quality.code.review(target="{target}", count=0, flag=False)', {}, None,
                    lambda *_: (logic, None))
    assert frame.arguments == {'target': '{target}', 'count': 0, 'flag': False,
                               'label': 'literal {target} # stays'}
    with pytest.raises(TypeError, match='keyword'):
        prepare('workflow.quality.code.review("alarm")', {}, None, lambda *_: (logic, None))


def test_call_data_expressions_filter_tickets_and_keep_assignment_text_literal():
    target = SimpleNamespace(work=[SimpleNamespace(condition='broken'), SimpleNamespace(condition='unbuilt')])
    logic = Logic('logic', 'stable', 'run', '@STATE_INIT:\n {tickets} := PARAM\n {label} := PARAM\n')
    frame = prepare('workflow.repair.code.run(tickets=[t for t in this.work if t.condition == "broken"], '
                    'label="a:=b")', {}, target, lambda *_: (logic, None))
    assert frame.arguments['tickets'] == [target.work[0]]
    assert frame.arguments['label'] == 'a:=b'
    assert receive(frame, 'ignored', {'old': True}) == {'old': True}


def test_single_tuple_target_unpacks_while_a_single_variable_keeps_the_tuple():
    logic = Logic('logic', 'stable', 'run', '@STATE_INIT:\n@CONSTRAINT:\n')
    lookup = lambda *_: (logic, None)
    tuple_target = prepare('({answer},) := workflow.quality.code.run()', {}, None, lookup)
    variable_target = prepare('{answer} := workflow.quality.code.run()', {}, None, lookup)
    assert receive(tuple_target, (True,), {}) == {'answer': True}
    assert receive(variable_target, (True,), {}) == {'answer': (True,)}


def test_map_element_values_pass_through_composed_calls_and_serialize_for_the_agent(store):
    small_map(store)
    element = store.element('code.timer.kitchen')
    sources = knowledge(store, 'sources')  # an element's refs are items of the sources layer
    store.add_item(sources.name, Node('element', element.id), 'code.timer.kitchen',
                   refs=[('path', 'src/timer.c')])
    store.finish(sources.name)
    layer = knowledge(store, 'procedures')
    store.add_element(layer.name, 'workflow.quality.code', name='Code Quality', name_length=2)
    store.finish(layer.name)
    caller = element_value(store, 'code.timer.kitchen')
    owner = element_value(store, 'workflow.quality.code')
    logic = Logic('logic', 'stable', 'review', REVIEW)
    frame = prepare('( {ok}, {issues} ) := workflow.quality.code.review('
                    'target=this, paths=this.refs.get("path"))', {}, caller, lambda *_: (logic, owner))
    payload = plain(frame)
    assert payload['arguments']['target']['address'] == 'code.timer.kitchen'
    assert payload['arguments']['paths'] == ['src/timer.c']
    assert payload['this']['address'] == 'workflow.quality.code'
    assert payload['logic']['content'] == REVIEW
    assert 'element_id' not in payload['arguments']['target']
    result = returned('RETURN ( TRUE, {target}.require["code.alarm.audible"].purpose )',
                      frame.arguments, frame.this)
    assert receive(frame, result, {}) == {'ok': True, 'issues': 'Get attention when a countdown ends.'}
