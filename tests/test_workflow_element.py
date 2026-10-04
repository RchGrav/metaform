"""MAP-057: the values handed to logic belong to its element, without storage identities."""
import json
from pathlib import Path

import pytest
from storekit import knowledge, memory, small_map

from metaform.data import Node, Store
from metaform.module import Context
from metaform.modules import memory as memory_module
from metaform.modules.workflow.element import element_value

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('MAP-057')]


@pytest.fixture
def mapped(store):
    layer, _, inner = small_map(store)
    element = store.element('code.timer.kitchen')
    store.refine(element.element_id, {'name': 'Kitchen Clock'}, reason='record the project name')
    store.refine(inner.join_id, {'ifd': 'receives'}, reason='record encounter details')
    sources = knowledge(store, 'sources')  # an element's refs are items of the sources layer, Rich 2026-10-04
    store.add_item(sources.name, Node('element', element.element_id), 'code.timer.kitchen',
                   refs=[('path', 'src/timer.c'), ('path', 'src/clock.c')])
    store.finish(sources.name)
    notes = knowledge(store, 'quality.notes')
    store.add_item(notes.name, Node('element', element.element_id), {'guidance': ['Keep time.']},
                   read_first=True, always_show=True)
    store.add_property(notes.name, 'code.timer', 'timed')
    store.add_property(notes.name, 'code.timer.kitchen', 'audible')
    store.finish(notes.name)
    hidden = knowledge(store, 'hidden.notes')
    store.add_item(hidden.name, Node('element', element.element_id), 'hidden item')
    store.add_property(hidden.name, 'code.timer', 'hidden context')
    store.finish(hidden.name)
    store.hide(hidden.name)
    ticket = store.add_work(Node('element', element.element_id), 'broken', note='Drifts.', task='Fix timing.')
    store.plan_work(ticket.work_id, 2)
    store.step_work(ticket.work_id, 'Measured the drift.')
    closed = store.add_work(Node('element', element.element_id), 'missing', task='Past task.')
    store.finish_work(closed.work_id, 'Already done.')
    store.ask(Node('element', element.element_id), 'Which tone?', suggestions=['Bell', 'Beep'])
    store.tell(Node('element', element.element_id), 'Check timing.')
    answered = store.ask(Node('element', element.element_id), 'Use a bell?', suggestions=['Yes'])
    store.reply(answered.message_id, 'Yes')
    memory(store)
    mem_store = Store(store.project_id, module='memory')
    ctx = Context('memory', Path(store.project().path), store=mem_store, nouns={
        'node': 'element:code.timer.kitchen', 'text': 'A precise clock.', 'by': 'Rich'})
    memory_module.note(ctx)
    ctx.nouns = {'node': 'element:code.timer.kitchen', 'entities': [
        {'name': 'drift', 'entityType': 'behavior', 'observations': ['Drifts under load.']}]}
    memory_module.create_entities(ctx)
    return store, layer, inner


def test_this_reads_the_complete_element_values(mapped):
    store, layer, _ = mapped
    this = element_value(store, 'code.timer.kitchen')
    assert (this.address, this.name, this.name_length, this.short_name, this.role, this.parent, this.layer) == (
        'code.timer.kitchen', 'Kitchen Clock', 2, 'kitchen timer', 'DE', 'code.timer', layer.name)
    assert isinstance(this.refs['path'], list)
    assert this.refs['path'] == ['src/timer.c', 'src/clock.c']
    alarm = this.require['code.alarm.audible']
    assert (alarm.purpose, alarm.ef, alarm.ifd, alarm.elements) == (
        'Get attention when a countdown ends.', 'Plays a tone.', 'receives', ['code.alarm.audible'])
    provided = this.provides['stakeholder.cook.home']
    assert (provided.purpose, provided.ef, provided.ifd, provided.elements) == (
        'Know when each dish is done.', 'Counts down and rings.', None, ['code.timer.kitchen', 'code.loop.tick'])
    assert this.items['quality.notes'][0].to_dict() == {
        'value': {'guidance': ['Keep time.']}, 'read_first': True, 'always_show': True}
    assert [p.value for p in this.properties['quality.notes']] == ['audible']
    assert [(p.address, p.value) for p in this.context] == [('code.timer', 'timed'), ('code.timer.kitchen', 'audible')]
    assert this.note.text == 'A precise clock.' and this.note.by == 'Rich' and this.note.at
    assert this.memories[0].to_dict() == {
        'name': 'drift', 'entity_type': 'behavior', 'observations': ['Drifts under load.']}
    assert [w.to_dict() for w in this.work] == [
        {'condition': 'broken', 'note': 'Drifts.', 'task': 'Fix timing.', 'steps': 2, 'steps_done': 1}]
    assert [m.to_dict() for m in this.messages] == [
        {'kind': 'question', 'text': 'Which tone?', 'answer': None},
        {'kind': 'message', 'text': 'Check timing.', 'answer': None}]
    plain = json.loads(json.dumps(this.to_dict()))
    assert set(plain) == {'address', 'name', 'name_length', 'short_name', 'role', 'parent', 'layer', 'refs',
                          'require', 'provides', 'items', 'properties', 'context', 'note', 'memories', 'work', 'messages'}
    assert set(plain['require']['code.alarm.audible']) == {'purpose', 'ef', 'ifd', 'elements'}
    assert this.items.get('hidden.notes') is None
    assert this.properties.get('hidden.notes') is None
    with pytest.raises(AttributeError):
        _ = this.extra
    with pytest.raises(AttributeError):
        _ = this.element_id


def test_this_is_read_only_and_missing_keys_keep_python_semantics(mapped):
    store, _, _ = mapped
    this = element_value(store, 'code.timer.kitchen')
    assert this.require.get('code.absent') is None
    with pytest.raises(KeyError):
        _ = this.require['code.absent']
    with pytest.raises(AttributeError):
        this.address = 'code.other'
    with pytest.raises(TypeError):
        this.require['code.other'] = None
    with pytest.raises(TypeError):
        this.refs['path'].append('changed')
    with pytest.raises(TypeError):
        this.items['quality.notes'][0].value['guidance'][0] = 'changed'
    copied = this.to_dict()
    copied['refs']['path'].append('only in the copy')
    assert this.refs['path'] == ['src/timer.c', 'src/clock.c']


def test_this_obeys_layer_selection_and_empty_fields(mapped):
    store, layer, _ = mapped
    this = element_value(store, 'code.timer.kitchen', selection=[layer.name])
    assert this.items['quality.notes'][0].always_show is True
    assert this.properties.get('quality.notes') is None
    assert this.context == [] and this.memories == []
    assert this.note.text == 'A precise clock.'
    cook = element_value(store, 'stakeholder.cook.home')
    assert cook.name is None and cook.note is None and cook.work == [] and cook.messages == []
    root = element_value(store, 'code.timer')
    assert root.parent == 'code'
    with pytest.raises(KeyError):
        element_value(store, 'code.absent')
