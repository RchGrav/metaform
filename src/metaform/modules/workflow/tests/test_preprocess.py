"""Prepared prompts carry chosen knowledge without changing their authored body."""
import json

import pytest

from metaform.data import Node, Store, StoreError
from metaform.modules.workflow.preprocess import assemble
from tests.storekit import PROVENANCE, small_map

pytestmark = [pytest.mark.req('LAYER-017'), pytest.mark.req('LAYER-007'), pytest.mark.kind('fixture')]


def knowledge(store, name, *, ready=True, tags=(), sources=()):
    return store.layer(name, 'test', 'Knowledge for this task.', mutable=True, hideable=True,
                       provenance=PROVENANCE, ready=ready, tags=tags, sources=sources)


def test_body_then_knowledge_then_canonical_footer_with_duplicates_removed(store):
    small_map(store)
    knowledge(store, 'practices')
    body = '  Review the kitchen timer.\nKeep this line.  \n'
    value = {'rule': 'Preserve countdown precision.', 'disabled': False, 'count': 0}
    store.add_item('practices', Node('element', 'code.timer.kitchen'), value)
    result = assemble(store, body, ['code.timer.kitchen', 'code.alarm.audible', 'code.timer.kitchen'])
    assert result['addresses'] == ['code.timer.kitchen', 'code.alarm.audible']
    assert result['scope'] == 'context'
    prepared = result['prompt']
    assert prepared.startswith(body)
    assert prepared.index('Preserve countdown precision.') > len(body)
    assert prepared.endswith('kitchen timer -> code.timer.kitchen\naudible alarm -> code.alarm.audible')
    assert prepared.count('kitchen timer -> code.timer.kitchen') == 1
    assert json.loads(prepared[len(body):].split('Knowledge layers:\n', 1)[1].rsplit('\n\n', 1)[0]) == result['layers']
    assert result['layers'][0]['items'][0]['value'] == value


def test_context_uses_inherited_and_visible_properties_and_never_other_node_items(store):
    layer, _, _ = small_map(store)
    store.add_element(layer.name, 'code.timer', role='SE')
    store.add_element(layer.name, 'code.timer.kitchen.display', role='SE')
    knowledge(store, 'practices')
    store.add_property('practices', 'code.timer', 'Inherited timer practice.')
    store.add_property('practices', 'code.timer.kitchen', 'Local practice.')
    store.add_property('practices', 'code.timer.kitchen.display', 'Visible display practice.')
    store.add_item('practices', Node('element', 'code.alarm.audible'), 'Alarm-only practice.')
    result = assemble(store, 'Review.', ['code.timer.kitchen', 'code.timer.kitchen.display'])
    properties = result['layers'][0]['properties']
    assert [one['value'] for one in properties] == [
        'Local practice.', 'Inherited timer practice.', 'Visible display practice.']
    assert 'Alarm-only practice.' not in result['prompt']


def test_masks_hidden_building_and_toggles_do_not_leak_knowledge(store):
    layer, _, _ = small_map(store)
    for name in ('chosen', 'excluded', 'hidden', 'derived', 'building'):
        knowledge(store, name, ready=name != 'building', tags=('task',) if name == 'chosen' else (),
                  sources=('hidden',) if name == 'derived' else ())
        store.add_item(name, Node('element', 'code.timer.kitchen'), f'{name} content.')
    store.hide('hidden')
    store.mask('code.timer', 'chosen')
    active = Store(store.project_id, toggled=(layer.name, 'task'))
    masked = assemble(active, 'Review.', ['code.timer.kitchen'])
    assert masked['layers'] == []
    store.select('code.timer.kitchen', 'chosen')
    restored = assemble(active, 'Review.', ['code.timer.kitchen'])
    assert [one['layer'] for one in restored['layers']] == ['chosen']
    assert 'chosen content.' in restored['prompt']
    for excluded in ('excluded', 'hidden', 'derived', 'building'):
        assert f'{excluded} content.' not in restored['prompt']


def test_whole_includes_available_layer_elsewhere_but_obeys_masks_at_each_origin(store):
    small_map(store)
    knowledge(store, 'practices')
    knowledge(store, 'excluded')
    store.add_item('practices', Node('element', 'code.timer.kitchen'), 'Timer practice.')
    store.add_item('practices', Node('element', 'code.alarm.audible'), 'Alarm practice.')
    store.add_item('practices', Node('element', 'code.loop.tick'), 'Masked tick practice.')
    store.add_item('excluded', Node('element', 'code.alarm.audible'), 'Excluded layer practice.')
    store.mask('code.loop', 'practices')
    store.mask('code.timer', 'excluded')
    result = assemble(store, 'Review.', ['code.timer.kitchen'], scope='whole')
    assert 'Timer practice.' in result['prompt'] and 'Alarm practice.' in result['prompt']
    assert 'Masked tick practice.' not in result['prompt']
    assert 'Excluded layer practice.' not in result['prompt']
    assert [one['address'] for one in result['layers'][0]['items']] == ['code.timer.kitchen', 'code.alarm.audible']


def test_whole_properties_obey_visibility_at_their_linked_addresses(store):
    small_map(store)
    knowledge(store, 'practices')
    store.add_property('practices', 'code.timer.kitchen', 'Timer property.')
    store.add_property('practices', 'code.alarm.audible', 'Alarm property.')
    store.add_property('practices', 'code.loop.tick', 'Masked tick property.')
    store.mask('code.loop', 'practices')
    result = assemble(store, 'Review.', ['code.timer.kitchen'], scope='whole')
    assert {one['value'] for one in result['layers'][0]['properties']} == {'Timer property.', 'Alarm property.'}
    assert 'Masked tick property.' not in result['prompt']


def test_missing_or_invisible_addresses_fail_without_substituting_raw_context(store):
    small_map(store)
    with pytest.raises(StoreError, match='not an element in the current context'):
        assemble(store, 'Review.', ['code.missing'])
    knowledge(store, 'optional')
    store.add_element('optional', 'code.optional', name='optional feature')
    store.mask('code.optional', 'optional')
    with pytest.raises(StoreError, match='not an element in the current context'):
        assemble(store, 'Review.', ['code.optional'])


@pytest.mark.req('LAYER-021')
@pytest.mark.parametrize('scope', ['context', 'whole'])
def test_always_show_retains_the_store_visibility_exception_without_broadening_its_layer(store, scope):
    layer, _, _ = small_map(store)
    for name in ('masked', 'hidden', 'untoggled', 'building'):
        knowledge(store, name, ready=name != 'building')
        store.add_item(name, Node('element', 'code.timer.kitchen'), f'{name} warning.', always_show=True)
        store.add_item(name, Node('element', 'code.timer.kitchen'), f'{name} ordinary content.')
        store.add_item(name, Node('element', 'code.alarm.audible'), f'{name} other address.', always_show=True)
    store.mask('code.timer', 'masked')
    store.hide('hidden')
    active = Store(store.project_id, toggled=(layer.name,))
    result = assemble(active, 'Review.', ['code.timer.kitchen'], scope=scope)
    for name in ('masked', 'hidden', 'untoggled'):
        assert f'{name} warning.' in result['prompt']
        assert f'{name} ordinary content.' not in result['prompt']
        assert f'{name} other address.' not in result['prompt']
    assert 'building warning.' not in result['prompt']
    assert all(one['always_show'] for group in result['layers'] for one in group['items'])


def test_empty_addresses_preserve_body_and_invalid_scope_reports_valid_choices(store):
    assert assemble(store, 'Keep exactly.\n', [])['prompt'] == 'Keep exactly.\n'
    with pytest.raises(StoreError, match='context or whole'):
        assemble(store, 'Review.', [], scope='raw')


def test_footer_without_a_canonical_name_uses_the_address_and_reports_it(store):
    small_map(store)
    result = assemble(store, 'Review.', ['stakeholder.cook.home'])
    assert result['prompt'].endswith('stakeholder.cook.home -> stakeholder.cook.home')
    assert result['notices'] == [{'where': 'stakeholder.cook.home',
                                 'message': 'No canonical name is recorded; the footer uses the namespace address.'}]


@pytest.mark.parametrize('addresses', [
    'code.timer.kitchen', {'address': 'code.timer.kitchen'}, None,
    [''], ['  '], [3], [False], [['code.timer.kitchen']], [{'address': 'code.timer.kitchen'}],
    ['code.timer.kitchen', 3],
])
def test_invalid_address_collections_raise_a_domain_error(store, addresses):
    with pytest.raises(StoreError, match='sequence of nonempty namespace strings'):
        assemble(store, 'Review.', addresses)
