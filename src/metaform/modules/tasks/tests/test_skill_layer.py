"""The skill layer stays ordinary scoped knowledge, with exact selected bodies."""
from __future__ import annotations

import hashlib
import json

import pytest
import yaml

from metaform import home, loader, skills
from metaform.data import Item, Join, Node
from metaform.module import Stop, context
from metaform.modules.tasks import skill_layer

pytestmark = pytest.mark.kind('fixture')


def document(name, body, description='Selected project skill.', **fields):
    header = {'name': name, 'description': description, **fields}
    return '---\n' + yaml.safe_dump(header, sort_keys=False) + '---\n' + body


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv('METAFORM_HOME', str(tmp_path / 'home'))
    loader.reset()
    folder = tmp_path / 'project'
    folder.mkdir()
    home.add_project('skill-layer-test', folder)
    ctx = context('tasks', folder, project='skill-layer-test')
    store = ctx.require_store()
    base = store.layer('functional-map', 'map', 'The functional map.', kind='base',
                       mutable=False, hideable=False)
    for address in ('code', 'code.receiver', 'code.provider', 'code.sibling'):
        store.add_element(base.name, address, name=address, role='SE')
    joined = store.add_join(base.name, 'code.receiver', ['code.provider'], purpose='Receive a result.',
                            ef='Return the provided result.')
    assert isinstance(joined, Join)
    store.finish(base.name)
    yield ctx, store, joined, base
    loader.reset()


def test_skill_layer_is_one_ordinary_layer_with_items_at_existing_nodes(project):
    ctx, store, joined, base = project
    before = store.layer_graph(base.name)
    element = skill_layer.put(ctx, 'code.receiver', 'canonical-skill-name', document('canonical-skill-name', '  Exact full instructions.\n'), 'A description.')
    on_join = skill_layer.put(ctx, f'join:{joined.id}', 'join-skill', document('join-skill', 'Inspect this purpose.'))
    after = store.layer_graph(base.name)
    assert after == before
    layer = store.layer_ref(skill_layer.LAYER)
    assert layer.kind == 'layer' and layer.mutable and layer.hideable and layer.ready
    assert 'skill' in layer.tags
    assert len([one for one in store.layers(limit=0).results if one.name == skill_layer.LAYER]) == 1
    stored = store.layer_items(skill_layer.LAYER, limit=0).results
    assert len(stored) == 2 and all(isinstance(item, Item) for item in stored)
    assert {item.target for item in stored} == {
        store.node(Node('element', 'code.receiver')).node, Node('join', joined.id)}
    assert {item.extra['kind'] for item in stored} == {'project_agent_skill'}
    assert {one['id'] for one in skill_layer.catalog(ctx, 'code.receiver')} == {element['id'], on_join['id']}
    for item in skill_layer.catalog(ctx, 'code.receiver'):
        assert set(item) == {'id', 'name', 'description', 'node', 'uri', 'frontmatter', 'resources'}
        assert 'instructions' not in item and 'text' not in item and 'component' not in item


def test_arrival_scope_follows_actual_received_and_provided_joins_without_siblings(project):
    ctx, _, joined, _ = project
    receiver = skill_layer.put(ctx, 'code.receiver', 'receiver-skill', document('receiver-skill', 'Receiver instructions.'))
    joined_skill = skill_layer.put(ctx, f'join:{joined.id}', 'purpose-skill', document('purpose-skill', 'Join instructions.'))
    sibling = skill_layer.put(ctx, 'code.sibling', 'sibling-skill', document('sibling-skill', 'Sibling instructions.'))
    assert {item['id'] for item in skill_layer.catalog(ctx, 'code.receiver')} == {receiver['id'], joined_skill['id']}
    assert {item['id'] for item in skill_layer.catalog(ctx, 'code.provider')} == {joined_skill['id']}
    assert {item['id'] for item in skill_layer.catalog(ctx, f'join:{joined.id}')} == {receiver['id'], joined_skill['id']}
    assert skill_layer.catalog(ctx, 'code') == []
    assert skill_layer.catalog(ctx, 'code.sibling') == [sibling]
    assert skill_layer.catalog(ctx) == []
    with pytest.raises(Stop, match='No project agent skill'):
        skill_layer.read(ctx, joined_skill['id'], 'code.sibling')


def test_selected_body_and_graph_snapshot_are_exact_after_edit(project):
    ctx, store, _, base = project
    before = store.layer_graph(base.name)
    made = skill_layer.put(ctx, 'code.receiver', 'exact-cpp', document('exact-cpp', 'First instructions.'))
    body = document('exact-cpp', '\n  Keep this exact body, {project}, symbols <&>, and punctuation.\n',
                    license='MIT', metadata={'owner': 'Project team'}, compatibility='Use the project tools.')
    edited = skill_layer.put(ctx, 'code.receiver', 'exact-cpp', body, 'Updated description.', made['id'])
    assert edited['id'] == made['id']
    read = skill_layer.read(ctx, made['id'], 'code.receiver')
    assert read['name'] == 'exact-cpp'
    assert read['text'] == read['component']['text'] == body
    assert read['component']['rendered_fingerprint'] == hashlib.sha256(body.encode()).hexdigest()
    assert read['component']['source'] == {'kind': 'graph', 'layer': 'skills',
                                          'node': 'code.receiver', 'item_id': made['id']}
    assert read['attachment'] == {'layer': 'skills', 'node': 'code.receiver', 'item_id': made['id']}
    assert skill_layer.read(ctx, 'exact-cpp', 'code.receiver')['text'] == body
    assert store.layer_graph(base.name) == before


def test_exact_id_can_be_loaded_without_global_name_lookup(project):
    ctx, _, joined, _ = project
    made = skill_layer.put(ctx, f'join:{joined.id}', 'purpose-skill', document('purpose-skill', 'Only this selected body.'))
    assert skill_layer.read(ctx, made['id'])['text'] == document('purpose-skill', 'Only this selected body.')
    with pytest.raises(Stop, match='No project agent skill'):
        skill_layer.read(ctx, made['name'])
    ctx.nouns['node'] = 'code.provider'
    assert skill_layer.read(ctx, made['name'])['id'] == made['id']


def test_put_reuses_name_at_same_attachment_and_ambiguous_scoped_names_need_id(project):
    ctx, _, joined, _ = project
    first = skill_layer.put(ctx, 'code.receiver', 'same-name', document('same-name', 'First body.'))
    replaced = skill_layer.put(ctx, 'code.receiver', 'same-name', document('same-name', 'Updated body.'))
    assert replaced['id'] == first['id']
    second = skill_layer.put(ctx, f'join:{joined.id}', 'same-name', document('same-name', 'Distinct attachment.'))
    with pytest.raises(Stop, match='More than one'):
        skill_layer.read(ctx, 'same-name', 'code.receiver')
    assert skill_layer.read(ctx, first['id'], 'code.receiver')['text'] == document('same-name', 'Updated body.')
    assert skill_layer.read(ctx, second['id'], 'code.receiver')['text'] == document('same-name', 'Distinct attachment.')


def test_existing_layer_declaration_and_unrelated_items_are_preserved(project):
    ctx, store, _, _ = project
    store.layer('skills', 'existing-owner', 'Existing canonical declaration.',
                mutable=True, hideable=False, tags=('existing-tag',), ready=True)
    original = store.layer_ref('skills')
    store.add_item('skills', Node('element', 'code.receiver'), 'Ordinary evidence.')
    skill_layer.put(ctx, 'code.receiver', 'scoped-skill', document('scoped-skill', 'Selected instructions.'))
    assert store.layer_ref('skills') == original
    assert len(skill_layer.catalog(ctx, 'code.receiver')) == 1
    assert len(store.layer_items('skills', limit=0).results) == 2


def test_invalid_target_and_non_skill_id_do_not_change_map(project):
    ctx, store, _, base = project
    before = store.layer_graph(base.name)
    with pytest.raises(Stop, match='No functional node'):
        skill_layer.put(ctx, 'code.MissingCanonicalNode', 'Name', document('Name', 'Instructions.'))
    assert not any(layer.name == 'skills' for layer in store.layers(limit=0).results)
    skill_layer.put(ctx, 'code.receiver', 'valid', document('valid', 'Instructions.'))
    other = store.add_item('skills', Node('element', 'code.receiver'), 'Not a skill.')
    with pytest.raises(Stop, match='No project agent skill'):
        skill_layer.read(ctx, other.id)
    assert store.layer_graph(base.name) == before


def test_skill_cannot_be_edited_through_a_different_attachment(project):
    ctx, _, _, _ = project
    made = skill_layer.put(ctx, 'code.receiver', 'unmoved-skill', document('unmoved-skill', 'Original body.'))
    with pytest.raises(Stop, match='No project agent skill'):
        skill_layer.put(ctx, 'code.sibling', 'unmoved-skill', document('unmoved-skill', 'Wrong attachment.'), skill_id=made['id'])
    assert skill_layer.read(ctx, made['id'])['text'] == document('unmoved-skill', 'Original body.')


def test_receiver_inline_joins_and_direct_join_documents_serialize_with_resources(project):
    ctx, store, joined, base = project
    before = store.layer_graph(base.name)
    text = document('combined-skill', 'Use the attached reference.\n',
                    **{'allowed-tools': ['Read', 'Edit'], 'metadata': {'version': 7}})
    files = {'references/example.txt': '  Exact reference <&>.\n'}
    receiver = skill_layer.put(ctx, 'code.receiver', 'combined-skill', text, files=files)
    direct = skill_layer.put(ctx, f'join:{joined.id}', 'combined-skill', text, files=files)
    stored = {item.id: item for item in store.layer_items('skills', limit=0).results}
    inline = stored[receiver['id']].value
    assert set(inline) == {'joins'}
    assert len(inline['joins']) == 1
    for made, record in ((receiver, inline['joins'][0]), (direct, stored[direct['id']].value)):
        assert json.loads(json.dumps(record)) == record
        assert record['files'] == {'SKILL.md': text, **files}
        loaded = skill_layer.read(ctx, made['id'])
        assert skill_layer.read(ctx, loaded['uri'])['text'] == text
        expected = skills.document('combined-skill', text, files=files, uri=loaded['uri'])
        assert {key: loaded[key] for key in ('uri', 'frontmatter', 'resources')} == {
            key: expected[key] for key in ('uri', 'frontmatter', 'resources')}
        assert loaded['files']['references/example.txt'].encode() == expected['files']['references/example.txt']
        for path, raw in expected['files'].items():
            resource = next(one for one in loaded['resources'] if one['uri'].endswith('/' + path))
            assert resource['digest'] == 'sha256:' + hashlib.sha256(raw).hexdigest()
            assert resource['size'] == len(raw)
        assert loaded['frontmatter']['allowed-tools'] == ['Read', 'Edit']
        assert loaded['frontmatter']['metadata'] == {'version': 7}
    assert receiver['uri'] == 'skill://skills/code.receiver/combined-skill/SKILL.md'
    assert direct['uri'] == f'skill://skills/{joined.id}/combined-skill/SKILL.md'
    assert store.layer_graph(base.name) == before


def test_plain_skill_body_requires_an_explicit_description(project):
    ctx, _, _, _ = project
    with pytest.raises(ValueError, match='description'):
        skill_layer.put(ctx, 'code.receiver', 'plain-skill', 'Body without frontmatter.')
    made = skill_layer.put(ctx, 'code.receiver', 'plain-skill', 'Body without frontmatter.', 'Explicit purpose.')
    loaded = skill_layer.read(ctx, made['id'])
    expected = skills.document('plain-skill', 'Body without frontmatter.', 'Explicit purpose.', uri=loaded['uri'])
    assert loaded['text'] == expected['files']['SKILL.md'].decode()
    assert loaded['frontmatter'] == expected['frontmatter']


def test_invalid_skill_name_is_not_silently_normalized(project):
    ctx, store, _, _ = project
    with pytest.raises(ValueError, match='Skill name'):
        skill_layer.put(ctx, 'code.receiver', 'Canonical Name',
                      document('Canonical Name', 'Keep exact authored spelling.'))
    assert skill_layer.catalog(ctx, 'code.receiver') == []
    assert not any(layer.name == 'skills' for layer in store.layers(limit=0).results)


def test_resource_callback_serves_one_known_graph_document_with_identical_digests(project):
    ctx, _, joined, _ = project
    text = document('native-graph-skill', 'Load this exact document through the Skills extension.\n',
                    metadata={'source': 'project'})
    files = {'references/details.md': '# Exact reference\n'}
    made = skill_layer.put(ctx, f'join:{joined.id}', 'native-graph-skill', text, files=files)
    expected = skills.document('native-graph-skill', text, files=files, uri=made['uri'])
    assert skill_layer.resource(ctx, made['uri']) == expected
    assert skill_layer.resource(ctx, 'skill://some-other-skill/SKILL.md') is None
    assert skill_layer.resource(ctx, 'skill://skills/code.receiver/not-present/SKILL.md') is None
    assert skill_layer.resource(ctx, 'skill://skills/code.missing/not-present/SKILL.md') is None
    assert skill_layer.catalog(ctx) == []


def test_a_project_held_in_the_project_store_keeps_its_skills_at_its_elements(tmp_path, monkeypatch):
    """Review of 2026-11-18, F3: skill discovery resolved nodes through the old store, so an element held only in the
    project store could hold no skill. Its skills are records of the skills overlay at the element, offered at the
    element and at the elements its wants name or that want it."""
    from metaform import project as project_store
    from metaform.project import owner, service
    where = tmp_path / 'home'
    monkeypatch.setenv('METAFORM_HOME', str(where))
    loader.reset()
    folder = tmp_path / 'project'
    folder.mkdir()
    home.add_project('stored', folder)
    try:
        for address, wants in (('code.provider', []), ('code.receiver', [{
                'element': 'stored.code.provider', 'why': 'get a result', 'how': 'returns it', 'direction': 'receive'}]),
                               ('code.sibling', [])):
            assert project_store.run({'add': {f'stored.{address}': {'technical_name': ' '.join(reversed(address.split('.'))), 'name': address,
                                                                     'role': 'Supporting Element',
                                                                     **({'wants': wants} if wants else {})}}}) \
                == {'status': 'ok'}
        ctx = context('tasks', folder, project='stored')
        made = skill_layer.put(ctx, 'code.receiver', 'receiver-skill', document('receiver-skill', 'Do it this way.'))
        assert [one['id'] for one in skill_layer.catalog(ctx, 'code.provider')] == [made['id']]
        assert skill_layer.catalog(ctx, 'code.sibling') == []
        read = skill_layer.read(ctx, 'receiver-skill', 'code.receiver')
        assert read['id'] == made['id'] and 'Do it this way.' in read['text']
        assert skill_layer.read(ctx, made['uri'])['id'] == made['id']
        again = skill_layer.put(ctx, 'code.receiver', 'receiver-skill', document('receiver-skill', 'Now this way.'))
        assert again['id'] == made['id'] and 'Now this way.' in skill_layer.read(ctx, made['id'], 'code.receiver')['text']
        with pytest.raises(Stop, match='No functional node'):
            skill_layer.put(ctx, 'code.missing', 'x', document('x', 'y'))
        assert all(one.name != skill_layer.LAYER for one in ctx.require_store().layers(limit=0).results)
    finally:
        service.stop(where)
        owner.close_all()
        loader.reset()
