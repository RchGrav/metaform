"""STORE-024: each write operation writes exactly its rows, and each listed error writes nothing."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from storekit import PROVENANCE, diff, dump, knowledge, memory, small_map, store_file

from metaform.data import Node, StoreError

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
    work: Any
    fixed: Any = None


def build(store) -> World:
    _, outer, inner = small_map(store)
    k = knowledge(store, 'k')
    store.add_element(k.name, 'code.k.a')
    store.add_element(k.name, 'code.k.b')
    k_join = store.add_join(k.name, 'code.k.a', 'code.k.b', purpose='p', ef='f')
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
                   ef='restarts the loop')
    challenge = store.add_item(critic.name, Node('element', 'code.watchdog'), 'Nothing recovers a hung loop.')
    store.finish(critic.name)
    work = store.add_work(Node('element', 'code.k.a'), 'unbuilt', task='build a')
    return World(outer, inner, item, prop, finished_item, memo, challenge, k_join, work)


def refined(store, world):
    return store.refine(world.inner.id, {'ef': 'Plays a loud tone.'}, reason='louder')


CASES: dict[str, tuple[Callable, Callable, dict]] = {
    'layer': (lambda s, w: None,
              lambda s, w, c: s.layer('new', 'test', 'New.', mutable=True, hideable=True,
                                      provenance=PROVENANCE),
              {'ops': (1, 0)}),
    'layer with tags': (lambda s, w: None,
                        lambda s, w, c: s.layer('new', 'test', 'New.', mutable=True, hideable=True, provenance=PROVENANCE, tags=('x',)),
                        {'ops': (1, 0)}),
    'finish': (lambda s, w: None, lambda s, w, c: s.finish('k'), {'ops': (1, 0)}),
    'edit': (lambda s, w: None, lambda s, w, c: s.edit(w.item.id, {'value': 'changed'}), {'ops': (1, 0)}),
    'remove': (lambda s, w: None, lambda s, w, c: s.remove(w.item.id),
               {'ops': (1, 0)}),
    'discard': (lambda s, w: s.layer('draft', 'test', 'Draft.', mutable=True, hideable=True,
                                     provenance=PROVENANCE),
                lambda s, w, c: s.discard('draft'), {'ops': (1, 0)}),
    'add_element': (lambda s, w: None, lambda s, w, c: s.add_element('k', 'code.k.c'),
                    {'ops': (1, 0), 'objects': (1, 0)}),
    'add_element with its name_length and name': (
        lambda s, w: None, lambda s, w, c: s.add_element('k', 'code.k.c', name_length=1, name='c'),
        {'ops': (1, 0), 'objects': (1, 0)}),
    # A join is one row with one join_elements row for each element it holds, Rich's shape, 2026-10-04.
    'add_join': (lambda s, w: None,
                 lambda s, w, c: s.add_join('k', 'code.k.b', 'code.k.a', purpose='p', ef='f'),
                 {'ops': (1, 0), 'objects': (1, 0)}),
    'add_join holding two elements': (lambda s, w: s.add_element('k', 'code.k.c'),
                                      lambda s, w, c: s.add_join('k', 'code.k.b', ['code.k.a', 'code.k.c'],
                                                                 purpose='p', ef='f'),
                                      {'ops': (1, 0), 'objects': (1, 0)}),
    'edit elements': (lambda s, w: s.add_element('k', 'code.k.c'),
                      lambda s, w, c: s.edit(w.k_join.id, {'elements': ['code.k.b', 'code.k.c']}),
                      {'ops': (1, 0)}),
    'edit receiver': (lambda s, w: s.add_element('k', 'code.k.c'),
                      lambda s, w, c: s.edit(w.k_join.id, {'receiver': 'code.k.c'}),
                      {'ops': (1, 0)}),
    'add_ref': (lambda s, w: None, lambda s, w, c: s.add_ref(w.item.id, 'path', 'y'), {'ops': (1, 0)}),
    'add_item': (lambda s, w: None, lambda s, w, c: s.add_item('k', Node('element', 'code.k.b'), 'v'),
                 {'ops': (1, 0), 'objects': (1, 0)}),
    'add_property': (lambda s, w: None, lambda s, w, c: s.add_property('k', 'code.k.a', 'v'),
                     {'ops': (1, 0), 'objects': (1, 0)}),  # a property is in the objects registry too, item 1
    'answer': (lambda s, w: None, lambda s, w, c: s.answer(w.challenge.id, 'B'), {'challenge_states': (1, 0)}),
    'approve': (lambda s, w: s.answer(w.challenge.id, 'B'), lambda s, w, c: s.approve(w.challenge.id),
                {'challenge_states': (1, 1), 'plans': (1, 0)}),
    'add_plan': (lambda s, w: None, lambda s, w, c: s.add_plan('k', 'code.k.b', w.k_join.id),
                 {'plans': (1, 0)}),
    # A work record is one row of `work` and nothing else: no identity row, no layer row, no change to the map,
    # STORE-042; its work_id is an identity id in form and stability, STORE-007, and the `work` row is its identity.
    'add_work': (lambda s, w: None, lambda s, w, c: s.add_work(Node('element', 'code.k.b'), 'unbuilt', task='build b'),
                 {'work': (1, 0)}),
    'add_work on a join': (lambda s, w: None,
                           lambda s, w, c: s.add_work(Node('join', w.k_join.id), 'broken', held=True),
                           {'work': (1, 0)}),
    'edit_work': (lambda s, w: None, lambda s, w, c: s.edit_work(w.work.id, {'reviewed': True, 'task': 'b'}),
                  {'work': (1, 1)}),
    'finish_work': (lambda s, w: None, lambda s, w, c: s.finish_work(w.work.id, 'built'), {'work': (1, 1)}),
    'update_item': (lambda s, w: None, lambda s, w, c: s.update_item(w.memo.id, 'changed'), {'ops': (1, 0)}),
    'delete_item': (lambda s, w: None, lambda s, w, c: s.delete_item(w.memo.id),
                    {'ops': (1, 0)}),
    # A refinement is one more version of the thing in the metaform's own layer, made current at once; no layer is
    # written, LAYER-025.
    'refine': (lambda s, w: None,
               lambda s, w, c: s.refine(w.inner.id, {'ef': 'x'}, reason='r'),
               {'ops': (1, 0)}),
    'refine a removal': (lambda s, w: None,
                         lambda s, w, c: s.refine(w.outer.id, remove=True, reason='r'),
                         {'ops': (1, 0)}),
    'add_element into the finished intake': (lambda s, w: None, lambda s, w, c: s.add_element('intake-1', 'code.x'),
                                             {'ops': (1, 0), 'objects': (1, 0)}),
    'reexamined': (lambda s, w: (s.layer('built', 'test', 'Built.', mutable=True, hideable=True,
                                         provenance=PROVENANCE, sources=('intake-1',)),
                                 s.finish('built'), refined(s, w)),
                   lambda s, w, c: s.reexamined('built'), {'ops': (1, 0)}),
    'select': (lambda s, w: None, lambda s, w, c: s.select('code.timer', 'done'), {'ops': (1, 0)}),
    'mask': (lambda s, w: None, lambda s, w, c: s.mask('code.timer', 'done'), {'ops': (1, 0)}),
    'clear': (lambda s, w: s.mask('code.timer', 'done'), lambda s, w, c: s.clear('code.timer', 'done', 'mask'),
              {'ops': (1, 0)}),
    'hide': (lambda s, w: None, lambda s, w, c: s.hide('done'), {'ops': (1, 0)}),
    'unhide': (lambda s, w: s.hide('done'), lambda s, w, c: s.unhide('done'), {'ops': (1, 0)}),
    'tag': (lambda s, w: None, lambda s, w, c: s.tag('done', 'x'), {'ops': (1, 0)}),
    'untag': (lambda s, w: s.tag('done', 'x'), lambda s, w, c: s.untag('done', 'x'), {'ops': (1, 0)}),
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
    assert diff(before, dump(store_file(home, store)))['ops'] == (2, 0)
    before = dump(store_file(home, store))
    with pytest.raises(ValueError), store.atomic():
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
                                                                      ef='f')),
    # Only an element is a join end: a real join's id given as an element the join holds, or as its receiver, cannot
    # be read, STORE-010.
    'add_join holding a join': (lambda s, w: None,
                                lambda s, w: s.add_join('k', 'code.k.a', w.k_join.id, purpose='p', ef='f')),
    'add_join received by a join': (lambda s, w: None,
                                    lambda s, w: s.add_join('k', w.k_join.id, 'code.k.a', purpose='p', ef='f')),
    'add_ref unknown owner': (lambda s, w: None, lambda s, w: s.add_ref('0' * 32, 'path', 'x')),
    'edit_work unknown': (lambda s, w: None, lambda s, w: s.edit_work('0' * 32, {'task': 'x'})),
    'finish_work unknown': (lambda s, w: None, lambda s, w: s.finish_work('0' * 32, 'x')),
    'approve open': (lambda s, w: None, lambda s, w: s.approve(w.challenge.id)),
    'approve A': (lambda s, w: s.answer(w.challenge.id, 'A'), lambda s, w: s.approve(w.challenge.id)),
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
    'edit intake': (lambda s, w: None, lambda s, w: s.edit(w.outer.id, {'purpose': 'x'}), False, _unchanged),
    'edit memory': (lambda s, w: None, lambda s, w: s.edit(w.memo.id, {'value': 'x'}), False, _unchanged),
    'edit key not allowed': (lambda s, w: None,
                             lambda s, w: s.edit(w.k_join.id, {'colour': 'blue', 'purpose': 'new'}), True,
                             lambda s, w, got, before: s.joins('code.k.a', raw=True).results[0].purpose == 'new'),
    'edit text that is not text': (lambda s, w: None,
                                   lambda s, w: s.edit(w.k_join.id, {'purpose': {'a': 1}}), True,
                                   lambda s, w, got, before: s.joins('code.k.a', raw=True).results[0].purpose
                                   == '{"a": 1}'),
    'edit an element address': (lambda s, w: s.add_element('k', 'code.k.c'),
                                lambda s, w: s.edit(s.element('code.k.c', raw=True).id,
                                                    {'address': 'code.k.d'}), False,
                                lambda s, w, got, before: s.element('code.k.c', raw=True) is not None and
                                s.element('code.k.d', raw=True) is None),
    'remove intake': (lambda s, w: None, lambda s, w: s.remove(w.outer.id), False, _unchanged),
    'remove memory': (lambda s, w: None, lambda s, w: s.remove(w.memo.id), False, _unchanged),
    'remove still used': (lambda s, w: None, lambda s, w: s.remove(s.element('code.k.a', raw=True).id), True,
                          lambda s, w, got, before: s.element('code.k.a', raw=True) is None and
                          s.joins('code.k.b', 'provider', raw=True).results[0].orphaned),
    'discard intake': (lambda s, w: None, lambda s, w: s.discard('intake-1'), False, _unchanged),
    'discard memory': (lambda s, w: None, lambda s, w: s.discard('memory'), False, _unchanged),
    'add_element role in a knowledge layer': (lambda s, w: None,
                                              lambda s, w: s.add_element('k', 'code.k.y', role='BOGUS'), True,
                                              lambda s, w, got, before: got.role is None and [
                                                  item.value for item in s.layer_items('k', Node('element', 'code.k.y')).results]
                                              == [{'role': 'BOGUS'}]),
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
                               lambda s, w: s.add_property('k', Node('join', w.k_join.id), 'v'), True,
                               lambda s, w, got, before: got.orphaned),
    'add_property extra not an object': (lambda s, w: None,
                                         lambda s, w: s.add_property('k', 'code.k.a', 'v', extra='x'), True,
                                         lambda s, w, got, before: got.extra == {'value': 'x'}),
    'answer outside a blind-spot layer': (lambda s, w: None, lambda s, w: s.answer(w.memo.id, 'A'), True,
                                          lambda s, w, got, before: got.state == 'A'),
    'answer plan': (lambda s, w: None, lambda s, w: s.answer(w.challenge.id, 'plan'), False, _unchanged),
    'answer C without link': (lambda s, w: None, lambda s, w: s.answer(w.challenge.id, 'C'), True,
                              lambda s, w, got, before: got.state == 'C' and got.link is None),
    'answer after approval': (lambda s, w: (s.answer(w.challenge.id, 'B'), s.approve(w.challenge.id)),
                              lambda s, w: s.answer(w.challenge.id, 'A'), True,
                              lambda s, w, got, before: got.state == 'A'),
    'add_plan unknown element': (lambda s, w: None, lambda s, w: s.add_plan('k', 'code.nothing', None), True,
                                 _raw_element('code.nothing')),
    'add_work condition outside the three': (lambda s, w: None,
                                             lambda s, w: s.add_work(Node('element', 'code.k.b'), 'sideways'), True,
                                             lambda s, w, got, before: got.condition == 'sideways'),
    'add_work node that names nothing': (lambda s, w: None,
                                         lambda s, w: s.add_work(Node('element', 'code.nothing'), 'unbuilt'), True,
                                         lambda s, w, got, before: (got.node_kind, got.node_id, got.address) ==
                                         ('element', 'code.nothing', None)),
    'edit_work key not allowed': (lambda s, w: None,
                                  lambda s, w: s.edit_work(w.work.id, {'colour': 'red', 'task': 'c'}), True,
                                  lambda s, w, got, before: got.task == 'c'),
    'finish_work twice': (lambda s, w: s.finish_work(w.work.id, 'first'),
                          lambda s, w: s.finish_work(w.work.id, 'second'), False,
                          lambda s, w, got, before: got.resolution == 'first'),
    'update_item not memory': (lambda s, w: None, lambda s, w: s.update_item(w.item.id, 'x'), False,
                               _unchanged),
    'delete_item not memory': (lambda s, w: None, lambda s, w: s.delete_item(w.item.id), False, _unchanged),
    'refine a knowledge layer\'s join': (lambda s, w: None,
                                         lambda s, w: s.refine(w.k_join.id, {'ef': 'x'}, reason='r'),
                                         False, _unchanged),
    'refine key not allowed': (lambda s, w: None,
                               lambda s, w: s.refine(w.inner.id, {'colour': 'x', 'ef': 'y'}, reason='r'), True,
                               lambda s, w, got, before: got.fields['ef'] == 'y'),
    'refine an element address': (lambda s, w: None,
                                  lambda s, w: s.refine(s.element('code.timer.kitchen').id,
                                                        {'address': 'code.timer.egg'}, reason='r'),
                                  False, _unchanged),
    'hide a layer that is not hideable': (lambda s, w: None, lambda s, w: s.hide('intake-1'), False, _unchanged),
    'select at an address out of form': (lambda s, w: None, lambda s, w: s.select('Code..Timer', 'done'), True,
                                         lambda s, w, got, before: True),
    'add_element malformed': (lambda s, w: None, lambda s, w: s.add_element('k', 'code..x'), True,
                              lambda s, w, got, before: s.where('code..x', raw=True) is not None),
    'add_join unknown end': (lambda s, w: None,
                             lambda s, w: s.add_join('k', 'code.k.a', 'code.nothing', purpose='p', ef='f'), True,
                             lambda s, w, got, before: s.element('code.nothing', raw=True).layer == 'k'),
    'add_join to itself': (lambda s, w: None,
                           lambda s, w: s.add_join('k', 'code.k.a', 'code.k.a', purpose='p', ef='f'), True,
                           lambda s, w, got, before: got.receiver in [held.element_id for held in got.elements]),
    'add_join holding no element': (lambda s, w: None,
                                    lambda s, w: s.add_join('k', 'code.k.a', [], purpose='p', ef='f'), True,
                                    lambda s, w, got, before: got.elements == ()),
    # The metaform holds no refs, Rich 2026-10-04: an element's refs are items of the sources layer.
    'add_ref on the metaform': (lambda s, w: None, lambda s, w: s.add_ref(w.outer.id, 'path', 'x'), False,
                                _unchanged),
    # A ref that is not a key and a value, both text, is kept in the record's extra under refs, STORE-012.
    'add_item ref not text': (lambda s, w: None,
                              lambda s, w: s.add_item('k', Node('element', 'code.k.a'), 'v', refs=[('line', 12)]),
                              True, lambda s, w, got, before: _odd_refs(got, [['line', 12]])),
    'add_property ref not text': (lambda s, w: None,
                                  lambda s, w: s.add_property('k', 'code.k.b', 'v', refs=[('line', 12)]),
                                  True, lambda s, w, got, before: _odd_refs(got, [['line', 12]])),
    'edit ref not text': (lambda s, w: None,
                          lambda s, w: s.edit(w.item.id, {'refs': [('path', 'a.c'), ('line', 12)]}), True,
                          lambda s, w, got, before: _odd_refs(
                              s.layer_items('k', Node('element', 'code.k.a')).results[0], [['line', 12]], ('path', 'a.c'))),
    'edit refs on a join': (lambda s, w: None,
                            lambda s, w: s.edit(w.k_join.id, {'refs': [('path', 'a.c')]}), False, _unchanged),
    'refine refs on a join': (lambda s, w: None,
                              lambda s, w: s.refine(w.inner.id, {'refs': [('path', 'a.c')]}, reason='r'), False,
                              _unchanged),
}


def _odd_refs(record, odd, *pairs, **rest):
    """The record's refs are exactly `pairs`, and its extra holds the rest with the odd refs under refs."""
    return [(ref.key, ref.value) for ref in record.refs] == list(pairs) and record.extra == {**rest, 'refs': odd}


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


@pytest.mark.req('STORE-004')
@pytest.mark.req('STORE-012')
def test_an_edit_that_changes_refs_and_extra_together_keeps_the_records_split_from_both(home, store):
    """Records in refs and records in an extra each become items of their own, STORE-004. When one edit carries both,
    the refs' records were dropped: the extra branch replaced the split list instead of adding to it. Found by review,
    2026-10-06."""
    world = build(store)
    at = Node('element', 'code.k.a')
    before = len(store.layer_items('k', at).results)
    store.edit(world.item.id, {'refs': [{'file': 'a.c'}, {'file': 'b.c'}], 'extra': {'steps': [{'n': 1}]}})
    after = store.layer_items('k', at).results
    assert len(after) == before + 3, [(item.value, item.extra) for item in after]   # two from refs, one from the extra
