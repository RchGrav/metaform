"""Instruction content follows explicit scope toward leaves; evidence and sibling branches stay local."""
import asyncio
import json

import pytest

from metaform.data import Node
from metaform.module import context
from metaform.modules.intake import CHECKED_VARIABLE, assessment_store, migrate_assessments
from metaform.modules.map import knowledge
from tests.storekit import intake

pytestmark = pytest.mark.kind('simulation')


def test_cpp_bash_platformer_scope_masks_and_local_evidence(store, project_folder, run):
    base = intake(store, ready=False)
    for address in ('code', 'code.engine', 'code.engine.game', 'code.engine.game.controls',
                    'code.engine.game.rules', 'code.installer', 'code.installer.install'):
        store.add_element(base.name, address, name=address.rsplit('.', 1)[-1], role='SE')
    store.finish(base.name)
    for layer, root, scope, body in (
        ('code.cpp', 'code.cpp', 'code.engine', 'Use C++23 ownership rules.'),
        ('code.bash', 'code.bash', 'code.installer', 'Quote shell expansions.'),
        ('platformer', 'code.platformer', 'code.engine.game', 'Keep movement responsive.')):
        store.layer(layer, 'map', body, kind='layer', mutable=True, hideable=True)
        store.add_element(layer, root, name=layer, role='AT')
        store.add_item(layer, Node('element', root), body, extra={'instruction': True})
        store.add_item(layer, Node('element', root), 'Local inspection passed.')
        knowledge(context('map', project_folder, project='proj', nouns={
            'op': 'link-context', 'layer': layer, 'element': scope, 'content': root}))
        store.finish(layer)
    def content(address):
        return {one['layer']: [item['value'] for item in one['items']]
                for one in store.context(address).knowledge}
    assert content('code.engine.game.controls') == {
        'code.cpp': ['Use C++23 ownership rules.'], 'platformer': ['Keep movement responsive.']}
    assert content('code.installer.install') == {'code.bash': ['Quote shell expansions.']}
    assert content('code') == {}
    cli = json.loads(run('map', 'context', 'code.engine.game.controls', '--json', cwd=project_folder).stdout)
    assert {one['layer'] for one in cli['knowledge']} == {'code.cpp', 'platformer'}
    from metaform.modules.mcp.server import answer
    failed, text, structured = asyncio.run(answer(project_folder, 'map_context', {
        'address': 'code.engine.game.controls'}, session='scoped-worker'))
    assert not failed, text
    assert structured and {one['layer'] for one in structured['knowledge']} == {'code.cpp', 'platformer'}
    store.mask('code.engine.game.controls', 'code.cpp')
    assert content('code.engine.game.controls') == {'platformer': ['Keep movement responsive.']}
    assert 'code.cpp' in content('code.engine.game.rules')
    store.hide('platformer')
    assert content('code.engine.game.controls') == {}
    assert store.context('code.engine.game.controls', selection=[]).knowledge == ()


def test_checked_migration_keeps_provenance_without_erasing_useful_layer_content(store):
    base = intake(store, ready=False)
    element = store.add_element(base.name, 'document.screenplay.scene', name='scene', role='SE')
    store.finish(base.name)
    store.layer('checked', 'intake', CHECKED_VARIABLE, kind='layer', mutable=True, hideable=True, ready=True)
    marker = store.add_item('checked', Node('element', element.id), 'ok', refs=[('path', 'screenplay.md')])
    useful = store.add_item('checked', Node('element', element.id), 'The heading locates the scene.')
    assert migrate_assessments(store) == 1
    assert [one.id for one in store.layer_items('checked', limit=0).results] == [useful.id]
    with assessment_store(store).tables(write=False) as tx:
        [record] = tx.rows('assessments', limit=0).results
        assert record['source_item'] == marker.id and record['condition'] == 'ok'
        assert record['evidence']['refs'] == [{'key': 'path', 'value': 'screenplay.md'}]
    assert migrate_assessments(store) == 0


@pytest.mark.parametrize('kind,root,part,beneficiary,purpose,encounter,condition', [
    ('brownfield', 'code.web.flask', 'code.web.flask.routing', 'downstream.cqu.visitor',
     'Receive the requested page', 'Routes the request to its handler', 'OK'),
    ('greenfield', 'code.game.platformer', 'code.game.platformer.controls', 'downstream.cqu.player',
     'Control movement', 'Turns input into movement', 'MISS'),
    ('screenplay', 'document.screenplay', 'document.screenplay.scene.heading', 'downstream.cqu.director',
     'Locate the scene for production', 'Identifies place and time', 'BKN'),
])
def test_functional_intake_roundtrip_keeps_meaning_and_assessments(
        run, project_folder, monkeypatch, tmp_path, kind, root, part, beneficiary, purpose, encounter, condition):
    from metaform.data import Store, export_document, import_document
    def intake_call(*words):
        return json.loads(run('intake', *words, '--json', cwd=project_folder).stdout)
    intake_call('start')
    intake_call('element', root, 'role=AUE')
    intake_call('element', part, 'role=SE', f'condition={condition}',
                f'note={kind} functional observation', 'refs=[{"key":"path","value":"source.txt"}]')
    intake_call('element', beneficiary, 'role=CQU')
    intake_call('purpose', beneficiary, part, f'purpose={purpose}', f'ef={encounter}', 'ifd=receives')
    intake_call('finish', f'report={kind} mapped with its observed limitations.')
    before = intake_call('show')
    document = export_document(['proj'])
    monkeypatch.setenv('METAFORM_HOME', str(tmp_path / 'roundtrip-home'))
    import_document(document)
    copied = Store('proj')
    [join] = copied.graph().joins
    assert (join.receiver_address, join.elements[0].address, join.purpose, join.ef) == (
        beneficiary, part, purpose, encounter)
    assert not any(layer.name == 'checked' for layer in copied.layers(limit=0).results)
    assert before['elements'] and not any(one.element.address.endswith('.checked') for one in copied.graph().elements)
    after = intake_call('show')
    assert after['elements'] == before['elements'] and after['purposes'] == before['purposes']
    assert len(copied.work(open=True, limit=0).results) == (0 if condition == 'OK' else 1)
    if condition == 'OK':
        with assessment_store(copied).tables(write=False) as tx:
            assert tx.rows('assessments', limit=0).results
