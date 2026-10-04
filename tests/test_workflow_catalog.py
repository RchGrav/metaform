"""Workflow storage uses the native map lifecycle and keeps procedure portable."""
import json

import pytest
from storekit import PROVENANCE, knowledge, small_map

from metaform import home as metaform_home
from metaform.data import Node, Store, StoreError
from metaform.module import Context
from metaform.modules.workflow import catalog

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('BASE-051', 'MAP-056')]


@pytest.fixture(autouse=True)
def enabled_workflow(run):
    run('enable', 'workflow')

ADDRESS = 'workflow.quality.code'
SCRIPT = '@STATE_INIT:\n  {target} := PARAM\n@EXECUTE_PIPELINE (Review):\n  RETURN TRUE\n'


def test_catalog_lookup_and_node_read_follow_layer_masks(store, project_folder):
    catalog.submit_workflow(store, ADDRESS, 'procedures', name='Code quality')
    logic = catalog.submit_logic(store, ADDRESS, 'procedures', 'review', SCRIPT)
    assert catalog.lookup(store, ADDRESS, 'review')[0] == logic
    assert catalog.workflows(store)[0]['logic'] == ['review']
    node = Node('element', store.element(ADDRESS).element_id)
    ctx = Context('workflow', project_folder, store=store)
    assert catalog.node_read(ctx, node)['logic'][0]['content'] == SCRIPT
    store.mask('workflow.quality', 'procedures')
    with pytest.raises(KeyError):
        catalog.lookup(store, ADDRESS, 'review')
    assert catalog.workflows(store) == []
    assert catalog.node_read(ctx, node) is None


def test_logic_refinement_keeps_identity_and_every_content_version(store):
    catalog.submit_workflow(store, ADDRESS, 'procedures')
    first = catalog.submit_logic(store, ADDRESS, 'procedures', 'review', SCRIPT)
    second_text = SCRIPT.replace('TRUE', 'FALSE')
    second = catalog.submit_logic(store, ADDRESS, 'procedures', 'review', second_text)
    assert second.logic_id == first.logic_id
    assert catalog.lookup(store, ADDRESS, 'review')[0].content == second_text
    assert [entry['content'] for entry in catalog.history(store, ADDRESS, 'review', 'procedures')] == [
        SCRIPT, second_text]


def test_logic_attaches_to_an_element_a_join_holds_and_keeps_existing_building_layer_building(store):
    small_map(store)
    existing = knowledge(store, 'shared')
    catalog.submit_logic(store, 'code.loop.tick', existing.name, 'improve', SCRIPT)
    assert next(layer for layer in store.layers(limit=0).results if layer.name == existing.name).ready is None
    store.finish(existing.name)
    logic, owner = catalog.lookup(store, 'code.loop.tick', 'improve')
    assert owner.address == 'code.loop.tick'
    assert logic.content == SCRIPT
    assert [join.receiver_address for join in store.where(owner.address).provides] == ['stakeholder.cook.home']
    ctx = Context('workflow', store.project().path, store=store)
    node = Node('element', store.element(owner.address).element_id)
    assert catalog.node_read(ctx, node)['logic'][0]['name'] == 'improve'


def test_portable_workflow_restores_other_project_with_versions_and_provenance(store, tmp_path):
    catalog.submit_workflow(store, ADDRESS, 'procedures', name='Code quality', layers=('standards',),
                            provenance=PROVENANCE)
    original = catalog.submit_logic(store, ADDRESS, 'procedures', 'review', SCRIPT)
    catalog.submit_logic(store, ADDRESS, 'procedures', 'review', SCRIPT + '# exact revision\n')
    exported = json.loads(json.dumps(catalog.document(store, ADDRESS, 'procedures')))
    folder = tmp_path / 'other'
    folder.mkdir()
    metaform_home.add_project('other', folder)
    other = Store('other')
    catalog.ingest_document(other, exported)
    restored, owner = catalog.lookup(other, ADDRESS, 'review')
    assert restored.logic_id != original.logic_id
    assert restored.content == SCRIPT + '# exact revision\n'
    assert owner.name == 'Code quality'
    assert [entry['content'] for entry in catalog.history(other, ADDRESS, 'review', 'procedures')] == [
        SCRIPT, restored.content]
    source = exported['layer']['provenance']
    assert source['prompt'] == PROVENANCE['prompt']
    assert source['model'] == PROVENANCE['model']
    result = catalog.document(other, ADDRESS, 'procedures')
    assert result['layer']['provenance'] == source
    assert result['workflow']['selected_layers'] == ['standards']


def test_resubmitting_workflow_updates_name_and_selects_its_knowledge(store):
    catalog.submit_workflow(store, ADDRESS, 'procedures', name='First name', layers=('standards',))
    original = store.element(ADDRESS).element_id
    layer = knowledge(store, 'standards')
    store.add_item(layer.name, Node('element', original), 'Read the standard.')
    store.finish(layer.name)
    catalog.submit_logic(store, ADDRESS, 'procedures', 'review', SCRIPT)
    catalog.submit_workflow(store, ADDRESS, 'procedures', name='New name', layers=('standards',))
    _, owner = catalog.lookup(store, ADDRESS, 'review', selection=['procedures'])
    assert owner.name == 'New name'
    assert store.element(ADDRESS).element_id == original
    assert owner.items['standards'][0].value == 'Read the standard.'
    assert catalog.selected_layers(store, ADDRESS, selection=['procedures']) == ['standards']
    store.mask('workflow', 'procedures')
    assert catalog.selected_layers(store, ADDRESS, selection=['procedures']) == []


def test_native_edit_refusal_preserves_current_logic_and_version_history(store):
    small_map(store)
    first = catalog.submit_logic(store, 'code.timer.kitchen', 'intake-1', 'review', SCRIPT)
    with pytest.raises(StoreError, match='changes by refining'):
        catalog.submit_logic(store, 'code.timer.kitchen', 'intake-1', 'review', 'Replacement')
    assert catalog.lookup(store, 'code.timer.kitchen', 'review')[0] == first
    assert len(catalog.history(store, 'code.timer.kitchen', 'review', 'intake-1')) == 1


def test_portable_import_keeps_native_edit_after_logged_versions(store, tmp_path):
    catalog.submit_workflow(store, ADDRESS, 'procedures')
    original = catalog.submit_logic(store, ADDRESS, 'procedures', 'review', SCRIPT)
    current = SCRIPT + '# Changed through the native knowledge tools.\n'
    store.edit(original.logic_id, {'value': {'type': 'logic', 'name': 'audit', 'content': current}})
    exported = catalog.document(store, ADDRESS, 'procedures')
    folder = tmp_path / 'native-copy'
    folder.mkdir()
    metaform_home.add_project('native-copy', folder)
    other = Store('native-copy')
    catalog.ingest_document(other, exported)
    assert catalog.lookup(other, ADDRESS, 'audit')[0].content == current
    assert catalog.workflows(other)[0]['logic'] == ['audit']
    restored = catalog.history(other, ADDRESS, 'audit', 'procedures')
    assert [entry['content'] for entry in restored] == [SCRIPT, current]
    assert [entry['name'] for entry in restored] == ['review', 'audit']


def test_catalog_keeps_explicit_metaform_binding_when_active_metaform_changes(store):
    catalog.submit_workflow(store, ADDRESS, 'procedures')
    original = store.active_metaform()
    store.add_metaform('another')
    bound = Store(store.project_id, metaform=original.metaform_id)
    saved = catalog.submit_logic(bound, ADDRESS, 'procedures', 'review', SCRIPT)
    assert catalog.lookup(bound, ADDRESS, 'review')[0] == saved
    assert catalog.workflows(store) == []
