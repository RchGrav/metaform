"""STORE-024: each write operation writes exactly its rows, and each listed error writes nothing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pytest

from metaform.data import Node, StoreError
from storekit import PROVENANCE, correction, diff, dump, knowledge, memory, small_map, store_file

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('STORE-024')]


@dataclass
class World:
    outer: Any
    inner: Any
    item: Any
    prop: Any
    finished_item: Any
    memo: Any
    challenge: Any
    k_join: Any
    fixed: Any = None


def build(store) -> World:
    _, outer, inner = small_map(store)
    k = knowledge(store, 'k')
    store.add_element(k.name, 'code.k.a')
    store.add_element(k.name, 'code.k.b')
    k_join = store.add_join(k.name, 'code.k.a', 'code.k.b', purpose='p', function='f', relation='r', observation='o')
    item = store.add_item(k.name, Node('element', 'code.k.a'), 'a note')
    prop = store.add_property(k.name, 'code.k.b', 'a property')
    done = knowledge(store, 'done')
    finished_item = store.add_item(done.name, Node('element', 'code.timer.kitchen'), 'done note')
    store.finish(done.name)
    notes = memory(store)
    memo = store.add_item(notes.name, Node('element', 'code.timer.kitchen'), 'a memory')
    critic = knowledge(store, 'critic')
    store.add_element(critic.name, 'code.watchdog')
    store.add_join(critic.name, 'code.timer.kitchen', 'code.watchdog', purpose='recover from a hang',
                   function='restarts the loop', relation='The watchdog restarts the timer.', observation='none yet')
    challenge = store.add_item(critic.name, Node('element', 'code.watchdog'), 'Nothing recovers a hung loop.')
    store.finish(critic.name)
    return World(outer, inner, item, prop, finished_item, memo, challenge, k_join)


def fix_with_change(store, world):
    fix = correction(store, 'fix')
    store.correct(fix.name, world.inner.join_id, {'function': 'Plays a loud tone.'}, reason='louder')
    return fix


def added_by_finished_fix(store, world):
    fix = correction(store, 'fix')
    world.fixed = store.add_element(fix.name, 'code.fixed')
    store.finish(fix.name)


def finished_fix(store, world):
    fix = fix_with_change(store, world)
    store.finish(fix.name)
    return fix


CASES: dict[str, tuple[Callable, Callable, dict]] = {
    'layer': (lambda s, w: None,
              lambda s, w, c: s.layer('new', 'test', 'New.', mutable=True, hideable=True,
                                      provenance=PROVENANCE),
              {'layers': (1, 0), 'provenance': (1, 0)}),
    'layer with tags': (lambda s, w: None,
                        lambda s, w, c: s.layer('new', 'test', 'New.', mutable=True, hideable=True, provenance=PROVENANCE, tags=('x',)),
                        {'layers': (1, 0), 'provenance': (1, 0), 'layer_tags': (1, 0)}),
    'finish': (lambda s, w: None, lambda s, w, c: s.finish('k'), {'layers': (1, 1)}),
    'finish correction': (fix_with_change, lambda s, w, c: s.finish('fix'),
                          {'layers': (1, 1), 'correction_stack': (1, 0), 'current_joins': (1, 1)}),
    'edit': (lambda s, w: None, lambda s, w, c: s.edit(w.item.item_id, {'value': 'changed'}), {'items': (1, 1)}),
    'remove': (lambda s, w: None, lambda s, w, c: s.remove(w.item.item_id),
               {'items': (0, 1), 'current_items': (0, 1)}),
    'discard': (lambda s, w: s.layer('draft', 'test', 'Draft.', mutable=True, hideable=True,
                                     provenance=PROVENANCE),
                lambda s, w, c: s.discard('draft'), {'layers': (0, 1), 'provenance': (0, 1)}),
    'add_element': (lambda s, w: None, lambda s, w, c: s.add_element('k', 'code.k.c'),
                    {'element_ids': (1, 0), 'identities': (1, 0), 'elements': (1, 0), 'current_elements': (1, 0),
                     'address_elements': (1, 0), 'types': (1, 0)}),
    'add_element with its name_length and refs': (
        lambda s, w: None, lambda s, w, c: s.add_element('k', 'code.k.c', name_length=1, refs=[('path', 'c.c')]),
        {'element_ids': (1, 0), 'identities': (1, 0), 'elements': (1, 0), 'current_elements': (1, 0),
         'address_elements': (1, 0), 'types': (1, 0), 'refs': (1, 0)}),
    'add_join': (lambda s, w: None,
                 lambda s, w, c: s.add_join('k', 'code.k.b', 'code.k.a', purpose='p', function='f', relation='r',
                                            observation='o', refs=[('path', 'x')]),
                 {'join_ids': (1, 0), 'identities': (1, 0), 'joins': (1, 0), 'current_joins': (1, 0),
                  'refs': (1, 0)}),
    'add_subtype': (lambda s, w: None,
                    lambda s, w, c: s.add_subtype('k', w.k_join.join_id, 'code.k.b.part', function='f'),
                    {'subtype_ids': (1, 0), 'identities': (1, 0), 'subtypes': (1, 0), 'current_subtypes': (1, 0),
                     'types': (1, 0)}),
    'add_ref': (lambda s, w: None, lambda s, w, c: s.add_ref(w.k_join.join_id, 'path', 'y'), {'refs': (1, 0)}),
    'add_item': (lambda s, w: None, lambda s, w, c: s.add_item('k', Node('element', 'code.k.b'), 'v'),
                 {'item_ids': (1, 0), 'identities': (1, 0), 'items': (1, 0), 'current_items': (1, 0)}),
    'add_property': (lambda s, w: None, lambda s, w, c: s.add_property('k', 'code.k.a', 'v'),
                     {'properties': (1, 0), 'current_properties': (1, 0)}),
    'answer': (lambda s, w: None, lambda s, w, c: s.answer(w.challenge.item_id, 'B'), {'challenge_states': (1, 0)}),
    'approve': (lambda s, w: s.answer(w.challenge.item_id, 'B'), lambda s, w, c: s.approve(w.challenge.item_id),
                {'challenge_states': (1, 1), 'plans': (1, 0)}),
    'add_plan': (lambda s, w: None, lambda s, w, c: s.add_plan('k', 'code.k.b', w.k_join.join_id),
                 {'plans': (1, 0)}),
    'update_item': (lambda s, w: None, lambda s, w, c: s.update_item(w.memo.item_id, 'changed'), {'items': (1, 1)}),
    'delete_item': (lambda s, w: None, lambda s, w, c: s.delete_item(w.memo.item_id),
                    {'items': (0, 1), 'current_items': (0, 1)}),
    'correct': (lambda s, w: correction(s, 'fix'),
                lambda s, w, c: s.correct('fix', w.inner.join_id, {'function': 'x'}, reason='r'),
                {'joins': (1, 0)}),
    'peel': (finished_fix, lambda s, w, c: s.peel('fix'),
             {'layers': (1, 1), 'correction_stack': (0, 1), 'current_joins': (1, 1)}),
    'reexamined': (lambda s, w: (s.layer('built', 'test', 'Built.', mutable=True, hideable=True,
                                         provenance=PROVENANCE, sources=('intake-1',)),
                                 s.finish('built'), finished_fix(s, w)),
                   lambda s, w, c: s.reexamined('built'), {'reexamine': (0, 1)}),
    'select': (lambda s, w: None, lambda s, w, c: s.select('code.timer', 'done'), {'selections': (1, 0)}),
    'mask': (lambda s, w: None, lambda s, w, c: s.mask('code.timer', 'done'), {'selections': (1, 0)}),
    'clear': (lambda s, w: s.mask('code.timer', 'done'), lambda s, w, c: s.clear('code.timer', 'done', 'mask'),
              {'selections': (0, 1)}),
    'hide': (lambda s, w: None, lambda s, w, c: s.hide('done'), {'hidden_layers': (1, 0)}),
    'unhide': (lambda s, w: s.hide('done'), lambda s, w, c: s.unhide('done'), {'hidden_layers': (0, 1)}),
    'tag': (lambda s, w: None, lambda s, w, c: s.tag('done', 'x'), {'layer_tags': (1, 0)}),
    'untag': (lambda s, w: s.tag('done', 'x'), lambda s, w, c: s.untag('done', 'x'), {'layer_tags': (0, 1)}),
}


@pytest.mark.parametrize('case', sorted(CASES))
def test_an_operation_writes_exactly_its_rows(home, store, case):
    setup, act, expected = CASES[case]
    world = build(store)
    context = setup(store, world)
    before = dump(store_file(home, store))
    act(store, world, context)
    assert diff(before, dump(store_file(home, store))) == expected


def test_atomic_commits_every_write_together(home, store):
    build(store)
    before = dump(store_file(home, store))
    with store.atomic():
        store.add_item('k', Node('element', 'code.k.a'), 'one')
        with store.atomic():
            store.add_item('k', Node('element', 'code.k.a'), 'two')
        assert len(store.layer_items('k', Node('element', 'code.k.a')).results) == 3
    assert diff(before, dump(store_file(home, store)))['items'] == (2, 0)
    before = dump(store_file(home, store))
    with pytest.raises(ValueError):
        with store.atomic():
            store.add_item('k', Node('element', 'code.k.a'), 'three')
            with store.atomic():
                store.add_item('k', Node('element', 'code.k.a'), 'four')
            raise ValueError('abandon the block')
    assert dump(store_file(home, store)) == before


ERRORS: dict[str, tuple[Callable, Callable]] = {
    'finish unknown': (lambda s, w: None, lambda s, w: s.finish('ghost')),
    'discard unknown': (lambda s, w: None, lambda s, w: s.discard('ghost')),
    'add_element unknown layer': (lambda s, w: None, lambda s, w: s.add_element('ghost', 'code.x')),
    'add_join an end that is no element id': (lambda s, w: None,
                                              lambda s, w: s.add_join('k', 'code.k.a', '0' * 32, purpose='p',
                                                                      function='f', relation='r', observation='o')),
    'add_subtype unknown join': (lambda s, w: None,
                                 lambda s, w: s.add_subtype('k', '0' * 32, 'code.k.part', function='f')),
    'add_ref unknown owner': (lambda s, w: None, lambda s, w: s.add_ref('0' * 32, 'path', 'x')),
    'approve open': (lambda s, w: None, lambda s, w: s.approve(w.challenge.item_id)),
    'approve A': (lambda s, w: s.answer(w.challenge.item_id, 'A'), lambda s, w: s.approve(w.challenge.item_id)),
    'reexamined unknown': (lambda s, w: None, lambda s, w: s.reexamined('ghost')),
}


@pytest.mark.req('STORE-026')
@pytest.mark.parametrize('case', sorted(ERRORS))
def test_each_listed_error_names_one_next_step_and_writes_nothing(home, store, case):
    setup, act = ERRORS[case]
    world = build(store)
    setup(store, world)
    before = dump(store_file(home, store))
    with pytest.raises(StoreError) as refused:
        act(store, world)
    step = refused.value.next_step
    assert step and '\n' not in step
    assert dump(store_file(home, store)) == before


@pytest.mark.req('STORE-005')
@pytest.mark.parametrize('case', sorted(CASES))
def test_an_operation_reaches_every_row_through_an_index(home, store, traced, case):
    from storekit import plans, scans
    setup, act, _ = CASES[case]
    world = build(store)
    context = setup(store, world)
    traced.clear()
    act(store, world, context)
    bad = [(statement, found) for statement, lines in plans(home, store, traced) if (found := scans(lines))]
    assert bad == []



def _unchanged(s, w, got, before):
    return before is not None


def _raw_element(address):
    return lambda s, w, got, before: s.element(address, raw=True) is not None


NOTICES: dict[str, tuple[Callable, Callable, bool, Callable]] = {
    # name: (setup, act, whether rows change, check on the store afterwards)
    'layer empty variable': (lambda s, w: None,
                             lambda s, w: s.layer('new', 'test', '', mutable=True, hideable=True, provenance=PROVENANCE),
                             True, lambda s, w, got, before: got.variable == ''),
    'layer without provenance': (lambda s, w: None,
                                 lambda s, w: s.layer('new', 'test', 'New.', mutable=True, hideable=True),
                                 True, lambda s, w, got, before: s.provenance('new').module == 'test'),
    'layer name taken with other properties': (
        lambda s, w: None,
        lambda s, w: s.layer('k', 'test', 'Something else.', mutable=True, hideable=True, provenance=PROVENANCE),
        True, lambda s, w, got, before: got.name == 'k-2'),
    'finish twice': (lambda s, w: None, lambda s, w: s.finish('done'), False, _unchanged),
    'edit intake': (lambda s, w: None, lambda s, w: s.edit(w.outer.join_id, {'purpose': 'x'}), False, _unchanged),
    'edit finished correction': (added_by_finished_fix,
                                 lambda s, w: s.edit(w.fixed.element_id, {'extra': {'a': 1}}), False, _unchanged),
    'edit memory': (lambda s, w: None, lambda s, w: s.edit(w.memo.item_id, {'value': 'x'}), False, _unchanged),
    'edit key not allowed': (lambda s, w: None,
                             lambda s, w: s.edit(w.k_join.join_id, {'receiver': 'code.k.b', 'purpose': 'new'}), True,
                             lambda s, w, got, before: s.joins('code.k.a', raw=True).results[0].purpose == 'new'),
    'edit text that is not text': (lambda s, w: None,
                                   lambda s, w: s.edit(w.k_join.join_id, {'purpose': {'a': 1}}), True,
                                   lambda s, w, got, before: s.joins('code.k.a', raw=True).results[0].purpose
                                   == '{"a": 1}'),
    'edit address held by a subtype': (lambda s, w: s.add_element('k', 'code.k.c'),
                                       lambda s, w: s.edit(s.element('code.k.c', raw=True).element_id,
                                                           {'address': 'code.loop.tick'}), True,
                                       _raw_element('code.loop.tick')),
    'remove intake': (lambda s, w: None, lambda s, w: s.remove(w.outer.join_id), False, _unchanged),
    'remove memory': (lambda s, w: None, lambda s, w: s.remove(w.memo.item_id), False, _unchanged),
    'remove still used': (lambda s, w: None, lambda s, w: s.remove(s.element('code.k.a', raw=True).element_id), True,
                          lambda s, w, got, before: s.element('code.k.a', raw=True) is None and
                          s.joins('code.k.b', 'provider', raw=True).results[0].orphaned),
    'discard intake': (lambda s, w: None, lambda s, w: s.discard('intake-1'), False, _unchanged),
    'discard stacked correction': (finished_fix, lambda s, w: s.discard('fix'), False, _unchanged),
    'discard memory': (lambda s, w: None, lambda s, w: s.discard('memory'), False, _unchanged),
    'add_element intake after its write': (lambda s, w: None, lambda s, w: s.add_element('intake-1', 'code.x'),
                                           False, _unchanged),
    'add_element finished correction': (finished_fix, lambda s, w: s.add_element('fix', 'code.x'), False,
                                        _unchanged),
    'add_element role in a knowledge layer': (lambda s, w: None,
                                              lambda s, w: s.add_element('k', 'code.k.y', role='BOGUS'), True,
                                              lambda s, w, got, before: got.role is None),
    'add_ref intake owner': (lambda s, w: None, lambda s, w: s.add_ref(w.outer.join_id, 'path', 'x'), False,
                             _unchanged),
    'add_item unknown target': (lambda s, w: None,
                                lambda s, w: s.add_item('k', Node('element', 'code.nothing'), 'v'), True,
                                _raw_element('code.nothing')),
    'add_item at a type address': (lambda s, w: None,
                                   lambda s, w: s.add_item('k', Node('type', 'data.bill_of_materials'), 'v'), True,
                                   _raw_element('data.bill_of_materials')),
    'add_item unknown link': (lambda s, w: None,
                              lambda s, w: s.add_item('k', Node('element', 'code.k.a'), 'v',
                                                      link=Node('join', '0' * 32)), True,
                              lambda s, w, got, before: got.link == Node('join', '0' * 32)),
    'add_item extra not an object': (lambda s, w: None,
                                     lambda s, w: s.add_item('k', Node('element', 'code.k.a'), 'v', extra=[1]),
                                     True, lambda s, w, got, before: got.extra == {'value': [1]}),
    'add_item extra holding records': (
        lambda s, w: None,
        lambda s, w: s.add_item('k', Node('element', 'code.k.a'), 'v', extra={'steps': [{'n': 1}, {'n': 2}]}),
        True, lambda s, w, got, before: [item.value for item in s.layer_items('k', Node('element', 'code.k.a')).results
                                         if isinstance(item.value, dict) and 'steps' in item.value] ==
        [{'steps': {'n': 1}}, {'steps': {'n': 2}}]),
    'add_item a list of answers': (
        lambda s, w: None, lambda s, w: s.add_item('k', Node('element', 'code.k.b'), ['one', 'two']), True,
        lambda s, w, got, before: [item.value for item in s.layer_items('k', Node('element', 'code.k.b')).results
                                   if item.value in ('one', 'two')] == ['one', 'two']),
    'add_property unknown element': (lambda s, w: None, lambda s, w: s.add_property('k', 'code.nothing', 'v'), True,
                                     _raw_element('code.nothing')),
    'add_property on a join': (lambda s, w: None,
                               lambda s, w: s.add_property('k', Node('join', w.k_join.join_id), 'v'), True,
                               lambda s, w, got, before: got.orphaned),
    'add_property extra not an object': (lambda s, w: None,
                                         lambda s, w: s.add_property('k', 'code.k.a', 'v', extra='x'), True,
                                         lambda s, w, got, before: got.extra == {'value': 'x'}),
    'answer outside a blind-spot layer': (lambda s, w: None, lambda s, w: s.answer(w.memo.item_id, 'A'), True,
                                          lambda s, w, got, before: got.state == 'A'),
    'answer plan': (lambda s, w: None, lambda s, w: s.answer(w.challenge.item_id, 'plan'), False, _unchanged),
    'answer C without link': (lambda s, w: None, lambda s, w: s.answer(w.challenge.item_id, 'C'), True,
                              lambda s, w, got, before: got.state == 'C' and got.link is None),
    'answer after approval': (lambda s, w: (s.answer(w.challenge.item_id, 'B'), s.approve(w.challenge.item_id)),
                              lambda s, w: s.answer(w.challenge.item_id, 'A'), True,
                              lambda s, w, got, before: got.state == 'A'),
    'add_plan unknown element': (lambda s, w: None, lambda s, w: s.add_plan('k', 'code.nothing', None), True,
                                 _raw_element('code.nothing')),
    'update_item not memory': (lambda s, w: None, lambda s, w: s.update_item(w.item.item_id, 'x'), False,
                               _unchanged),
    'delete_item not memory': (lambda s, w: None, lambda s, w: s.delete_item(w.item.item_id), False, _unchanged),
    'correct in a knowledge layer': (lambda s, w: None,
                                     lambda s, w: s.correct('k', w.inner.join_id, {'function': 'x'}, reason='r'),
                                     False, _unchanged),
    'correct key not allowed': (lambda s, w: correction(s, 'fix'),
                                lambda s, w: s.correct('fix', w.inner.join_id, {'colour': 'x', 'function': 'y'},
                                                       reason='r'), True,
                                lambda s, w, got, before: got.fields['function'] == 'y'),
    'correct receiver': (lambda s, w: correction(s, 'fix'),
                         lambda s, w: s.correct('fix', w.inner.join_id, {'receiver': 'code.k.a'}, reason='r'),
                         False, _unchanged),
    'peel a knowledge layer': (lambda s, w: None, lambda s, w: s.peel('done'), False, _unchanged),
    'peel below the top': (lambda s, w: (finished_fix(s, w), correction(s, 'fix2'),
                                         s.correct('fix2', w.inner.join_id, {'function': 'z'}, reason='r'),
                                         s.finish('fix2')),
                           lambda s, w: s.peel('fix'), False, _unchanged),
    'select a correction layer': (finished_fix, lambda s, w: s.select('code.timer', 'fix'), False, _unchanged),
    'mask a correction layer': (finished_fix, lambda s, w: s.mask('code.timer', 'fix'), False, _unchanged),
    'hide a correction layer': (finished_fix, lambda s, w: s.hide('fix'), False, _unchanged),
    'hide a layer that is not hideable': (lambda s, w: None, lambda s, w: s.hide('intake-1'), False, _unchanged),
    'select at an address out of form': (lambda s, w: None, lambda s, w: s.select('Code..Timer', 'done'), True,
                                         lambda s, w, got, before: True),
    'add_element malformed': (lambda s, w: None, lambda s, w: s.add_element('k', 'code..x'), True,
                              lambda s, w, got, before: s.where('code..x', raw=True) is not None),
    'add_join unknown end': (lambda s, w: None,
                             lambda s, w: s.add_join('k', 'code.k.a', 'code.nothing', purpose='p', function='f',
                                                     relation='r', observation='o'), True,
                             lambda s, w, got, before: s.element('code.nothing', raw=True).layer == 'k'),
    'add_join to a subtype address': (lambda s, w: None,
                                      lambda s, w: s.add_join('k', 'code.k.a', 'code.loop.tick', purpose='p',
                                                              function='f', relation='r', observation='o'), True,
                                      lambda s, w, got, before: got.provider_address == 'code.loop.tick'),
    'add_join to itself': (lambda s, w: None,
                           lambda s, w: s.add_join('k', 'code.k.a', 'code.k.a', purpose='p', function='f',
                                                   relation='r', observation='o'), True,
                           lambda s, w, got, before: got.receiver == got.provider),
    'add_subtype malformed': (lambda s, w: None,
                              lambda s, w: s.add_subtype('k', w.k_join.join_id, 'Code.Part', function='f'), True,
                              lambda s, w, got, before: got.address == 'Code.Part'),
    'add_subtype purpose': (lambda s, w: None,
                            lambda s, w: s.add_subtype('k', w.k_join.join_id, 'code.k.part', function='f',
                                                       purpose='p'), True,
                            lambda s, w, got, before: got.extra == {'purpose': 'p'}),
    'add_subtype address held': (lambda s, w: None,
                                 lambda s, w: s.add_subtype('k', w.k_join.join_id, 'code.loop.tick', function='f'),
                                 True, lambda s, w, got, before: got.address == 'code.loop.tick'),
}


@pytest.mark.req('STORE-026')
@pytest.mark.req('BASE-044')
@pytest.mark.parametrize('case', sorted(NOTICES))
def test_each_condition_that_does_not_fit_is_a_notice_and_never_an_error(home, store, case):
    setup, act, writes, check = NOTICES[case]
    world = build(store)
    setup(store, world)
    before = dump(store_file(home, store))
    got = act(store, world)
    notices = getattr(got, 'notices', ())
    assert notices and all(notice.message and notice.where for notice in notices)
    after = dump(store_file(home, store))
    assert (after != before) is writes
    assert check(store, world, got, before)
