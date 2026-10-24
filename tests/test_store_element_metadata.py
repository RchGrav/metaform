"""Block assignments and explicit containment stay native element metadata."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest
from storekit import intake

from metaform.data import Node, Store, export_document, import_document
from metaform.finish_xml import xml

pytestmark = pytest.mark.kind('fixture')


def metadata_map(store, *, ready=True):
    layer = intake(store, ready=ready)
    parent = store.add_element(layer.name, 'code.system', name_length=1, name='system', role='DE',
                               block='BLOCK_001')
    child = store.add_element(layer.name, 'code.sensor.part', name_length=2, name='sensor part', role='SE',
                              block='BLOCK_002', within=parent.address)
    join = store.add_join(layer.name, parent.address, child.address, purpose='Read a measurement.',
                          ef='Supplies the measured value.', ifd='receives')
    return layer, parent, child, join


def test_creation_stores_block_and_explicit_parent_in_native_reads(store):
    layer, parent, child, _ = metadata_map(store)

    assert (child.block, child.within, child.notices) == ('BLOCK_002', parent.address, ())
    reopened = Store('proj')
    found = reopened.element(child.address)
    assert found.to_dict()['block'] == 'BLOCK_002'
    assert found.to_dict()['within'] == parent.address
    assert reopened.where(child.address).element == found
    graph = {entry.element.address: entry.element for entry in reopened.graph().elements}
    assert graph[child.address] == found
    fields = reopened.history(child.id).results[0].fields
    assert fields == {'address': child.address, 'name_length': 2, 'name': 'sensor part', 'role': 'SE',
                      'block': 'BLOCK_002', 'within': parent.address}
    assert reopened.element(parent.address).within is None
    assert [entry.id for entry in reopened.layers().results] == [layer.id]


def test_duplicate_add_keeps_metadata_and_reports_unapplied_values(store):
    layer, parent, child, _ = metadata_map(store)
    before = store.history(child.id).to_dict()

    repeated = store.add_element(layer.name, child.address)
    assert (repeated.block, repeated.within, repeated.existing, repeated.differs) == (
        'BLOCK_002', parent.address, True, False)
    changed = store.add_element(layer.name, child.address, block='BLOCK_003', within='code.other')
    assert changed.existing and changed.differs
    assert (changed.block, changed.within) == ('BLOCK_002', parent.address)
    assert [notice.where for notice in changed.notices] == ['block', 'within']
    assert store.history(child.id).to_dict() == before


def test_refinement_changes_each_field_and_clears_it_without_changing_map_or_refs(store):
    layer, parent, child, join = metadata_map(store)
    store.link_ref('path', 'src/sensor.py', Node('element', child.id))
    refs_before = [ref.to_dict() for ref in store.refs()]
    join_before = store.history(join.id).to_dict()
    expected = dict(store.history(child.id).results[0].fields)
    snapshots = [dict(expected)]

    for changes in ({'block': 'BLOCK_003'}, {'within': 'code.other'}, {'block': None}, {'within': None},
                    {'name': 'renamed sensor'}):
        expected.update(changes)
        refined = store.refine(child.id, changes, reason='Preserve the authored structure.')
        assert refined.notices == ()
        assert refined.fields == expected
        snapshots.append(dict(expected))
        current = store.element(child.address)
        assert (current.id, current.address, current.layer_id, current.name_length, current.role) == (
            child.id, child.address, layer.id, 2, 'SE')
        assert (current.block, current.within) == (expected['block'], expected['within'])

    assert [version.fields for version in store.history(child.id).results] == snapshots
    assert store.history(join.id).to_dict() == join_before
    assert [ref.to_dict() for ref in store.refs()] == refs_before
    assert store.element(parent.address).block == 'BLOCK_001'


def test_building_base_edit_preserves_omitted_metadata_and_clears_explicit_none(store):
    layer, _, child, _ = metadata_map(store, ready=False)
    expected = dict(store.history(child.id).results[0].fields)

    for changes in ({'block': 'BLOCK_004'}, {'within': 'code.other'}, {'block': None}, {'within': None},
                    {'block': 'BLOCK_005', 'within': 'code.system'}, {'name': 'edited sensor'}):
        expected.update(changes)
        edited = store.edit(child.id, changes)
        assert edited.notices == ()
        assert edited.fields == expected
        current = store.element(child.address, raw=True)
        assert (current.block, current.within) == (expected['block'], expected['within'])

    store.finish(layer.name)
    assert (store.element(child.address).block, store.element(child.address).within) == ('BLOCK_005', 'code.system')


@pytest.mark.parametrize('operation', ['add', 'edit', 'refine', 'grow'])
def test_metadata_uses_existing_text_conversion_and_notices(store, operation):
    layer = intake(store, ready=operation != 'edit')
    given = {'block': {'number': 7}, 'within': 12}
    if operation == 'add':
        result = store.add_element(layer.name, 'code.part', **given)
    elif operation == 'grow':
        result = store.grow_element('code.part', name='part', role='SE', reason='Record its block.', **given)
    else:
        part = store.add_element(layer.name, 'code.part')
        result = (store.edit(part.id, given) if operation == 'edit' else
                  store.refine(part.id, given, reason='Record its block.'))

    assert [notice.where for notice in result.notices] == ['block', 'within']
    found = store.element('code.part', raw=True)
    assert (found.block, found.within) == ('{"number": 7}', '12')
    assert [entry.id for entry in store.layers().results] == [layer.id]


def test_growth_records_metadata_and_provenance_in_the_existing_base(store):
    layer, parent, _, _ = metadata_map(store)

    grown = store.grow_element('code.controller', name_length=1, name='controller', role='SE',
                               block='BLOCK_006', within=parent.address, reason='A controller is present.',
                               evidence='src/controller.py', by='fixture')

    assert grown.notices == ()
    assert (grown.block, grown.within, grown.layer_id) == ('BLOCK_006', parent.address, layer.id)
    version = store.history(grown.id).results[0]
    assert (version.reason, version.evidence, version.by) == (
        'A controller is present.', 'src/controller.py', 'fixture')
    assert (version.fields['block'], version.fields['within']) == ('BLOCK_006', parent.address)
    assert [entry.id for entry in store.layers().results] == [layer.id]


@pytest.mark.parametrize('merge', [False, True])
def test_move_preserves_copied_metadata_and_existing_target_metadata(store, merge):
    layer, parent, child, join = metadata_map(store)
    destination = 'code.sensor.renamed'
    if merge:
        target = store.add_element(layer.name, destination, name='existing sensor', name_length=1, role='NE',
                                   block='BLOCK_099', within='code.other')
    else:
        target = child
    before = store.history(join.id).results[-1].fields

    moved = store.move(child.id, destination, reason='Use the correct address.')

    assert (moved.address, moved.name_length, moved.name, moved.role, moved.block, moved.within) == (
        destination, target.name_length, target.name, target.role, target.block, target.within)
    assert store.element(child.address) is None
    current = store.joins(parent.address).results[0]
    assert (current.id, current.purpose, current.ef, current.ifd) == (
        join.id, before['purpose'], before['ef'], before['ifd'])
    assert [held.address for held in current.elements] == [destination]
    old_version = store.history(child.id).results[-1]
    assert (old_version.op, old_version.fields['block'], old_version.fields['within']) == (
        'remove', child.block, child.within)


@pytest.mark.parametrize('merge', [False, True])
def test_parent_move_retargets_only_explicit_children_and_preserves_each_history(store, merge):
    layer, parent, child, join = metadata_map(store)
    destination = 'code.system.renamed'
    if merge:
        target = store.add_element(layer.name, destination, name='existing system', name_length=2, role='NE',
                                   block='BLOCK_099', within='code.other')
        target_history = store.history(target.id).to_dict()
    else:
        target = parent
    grandchild = store.add_element(layer.name, 'code.sensor.part.detail', name='detail', role='SE',
                                   block='BLOCK_003', within=child.address)
    implicit = store.add_element(layer.name, 'code.system.implicit', name='namespace child', role='SE',
                                 block='BLOCK_004')
    other = store.add_element(layer.name, 'code.other.part', name='another child', role='SE',
                              block='BLOCK_005', within=parent.address + '.other')
    store.refine(child.id, {'block': 'BLOCK_006'}, reason='Correct the block before renaming its parent.')
    child_history = store.history(child.id).to_dict()
    child_fields = dict(store.history(child.id).results[-1].fields)
    unchanged = {part.id: store.history(part.id).to_dict() for part in (grandchild, implicit, other)}
    join_fields = store.history(join.id).results[-1].fields

    moved = store.move(parent.id, destination, reason='Use the correct parent address.',
                        evidence='The authored structure.', by='fixture')

    assert (moved.name, moved.name_length, moved.role, moved.block, moved.within) == (
        target.name, target.name_length, target.role, target.block, target.within)
    if merge:
        assert moved.id == target.id
        assert store.history(target.id).to_dict() == target_history
    assert store.element(parent.address) is None
    found = store.element(child.address)
    assert (found.id, found.address, found.layer_id, found.name, found.role, found.block, found.within) == (
        child.id, child.address, child.layer_id, child.name, child.role, 'BLOCK_006', destination)
    after = store.history(child.id).to_dict()
    assert after['results'][:-1] == child_history['results']
    latest = after['results'][-1]
    assert latest['fields'] == {**child_fields, 'within': destination}
    assert (latest['reason'], latest['evidence'], latest['by']) == (
        'Use the correct parent address.', 'The authored structure.', 'fixture')
    assert {part.id: store.history(part.id).to_dict() for part in (grandchild, implicit, other)} == unchanged
    graph = {entry.element.address: entry.parent for entry in store.graph().elements}
    assert graph[child.address] == destination
    current_join = store.joins(destination).results[0]
    assert (current_join.id, current_join.purpose, current_join.ef, current_join.ifd) == (
        join.id, join_fields['purpose'], join_fields['ef'], join_fields['ifd'])


@pytest.mark.parametrize('legacy', [False, True])
def test_export_import_preserves_metadata_and_reads_versions_that_omit_it(store, monkeypatch, tmp_path, legacy):
    _, parent, child, join = metadata_map(store)
    store.link_ref('path', 'src/sensor.py', Node('element', child.id))
    if not legacy:
        store.refine(child.id, {'block': 'BLOCK_007'}, reason='Correct its assignment.')
    before = export_document(['proj'])
    if legacy:
        for op in before['projects'][0]['bases'][0]['ops']:
            if op['kind'] == 'element':
                op['data'].pop('block', None)
                op['data'].pop('within', None)

    monkeypatch.setenv('METAFORM_HOME', str(tmp_path / 'import-home'))
    import_document(json.loads(json.dumps(before)))

    assert export_document(['proj']) == before
    imported = Store('proj')
    found = imported.element(child.address)
    assert (found.id, found.name_length, found.name, found.role) == (child.id, 2, 'sensor part', 'SE')
    assert (found.block, found.within) == ((None, None) if legacy else ('BLOCK_007', parent.address))
    assert (found.to_dict()['block'], found.to_dict()['within']) == (found.block, found.within)
    current = imported.joins(parent.address).results[0]
    assert (current.id, current.purpose, current.ef, current.ifd) == (join.id, join.purpose, join.ef, join.ifd)
    assert [(ref.key, ref.value, ref.node.id) for ref in imported.refs()] == [('path', 'src/sensor.py', child.id)]


def test_xml_includes_recorded_metadata_and_keeps_default_attributes_when_absent(store):
    _, parent, child, _ = metadata_map(store)
    document = ET.fromstring(xml(store, parent.address))
    elements = {element.get('namespace_address'): element for element in document.iter('element')}
    assert elements[child.address].attrib == {
        'namespace_address': child.address, 'name_length': '2', 'name': 'sensor part', 'role': 'SE',
        'block': 'BLOCK_002', 'within': parent.address}
    assert elements[parent.address].get('block') == 'BLOCK_001'
    assert 'within' not in elements[parent.address].attrib

    store.refine(child.id, {'block': None, 'within': None}, reason='Clear optional metadata.')
    cleared = ET.fromstring(xml(store, child.address)).find('element')
    assert cleared.attrib == {
        'namespace_address': child.address, 'name_length': '2', 'name': 'sensor part', 'role': 'SE'}
