"""Project expertise stays ordinary scoped knowledge, with exact selected bodies."""
from __future__ import annotations

import hashlib
import json

import pytest
import yaml

from metaform import home, loader, skills
from metaform.data import Item, Join, Node
from metaform.module import Stop, context
from metaform.modules.tasks import expertise

pytestmark = pytest.mark.kind('fixture')


def document(name, body, description='Selected project expertise.', **fields):
    header = {'name': name, 'description': description, **fields}
    return '---\n' + yaml.safe_dump(header, sort_keys=False) + '---\n' + body


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv('METAFORM_HOME', str(tmp_path / 'home'))
    loader.reset()
    folder = tmp_path / 'project'
    folder.mkdir()
    home.add_project('expertise-test', folder)
    ctx = context('tasks', folder, project='expertise-test')
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


def test_expertise_is_one_ordinary_layer_with_items_at_existing_nodes(project):
    ctx, store, joined, base = project
    before = store.layer_graph(base.name)
    element = expertise.put(ctx, 'code.receiver', 'canonical-skill-name', document('canonical-skill-name', '  Exact full instructions.\n'), 'A description.')
    on_join = expertise.put(ctx, f'join:{joined.id}', 'join-expertise', document('join-expertise', 'Inspect this purpose.'))
    after = store.layer_graph(base.name)
    assert after == before
    layer = store.layer_ref(expertise.LAYER)
    assert layer.kind == 'layer' and layer.mutable and layer.hideable and layer.ready
    assert 'expertise' in layer.tags
    assert len([one for one in store.layers(limit=0).results if one.name == expertise.LAYER]) == 1
    stored = store.layer_items(expertise.LAYER, limit=0).results
    assert len(stored) == 2 and all(isinstance(item, Item) for item in stored)
    assert {item.target for item in stored} == {
        store.node(Node('element', 'code.receiver')).node, Node('join', joined.id)}
    assert {item.extra['kind'] for item in stored} == {'project_agent_skill'}
    assert {one['id'] for one in expertise.catalog(ctx, 'code.receiver')} == {element['id'], on_join['id']}
    for item in expertise.catalog(ctx, 'code.receiver'):
        assert set(item) == {'id', 'name', 'description', 'node', 'uri', 'frontmatter', 'resources'}
        assert 'instructions' not in item and 'text' not in item and 'component' not in item


def test_arrival_scope_follows_actual_received_and_provided_joins_without_siblings(project):
    ctx, _, joined, _ = project
    receiver = expertise.put(ctx, 'code.receiver', 'receiver-skill', document('receiver-skill', 'Receiver instructions.'))
    joined_skill = expertise.put(ctx, f'join:{joined.id}', 'purpose-skill', document('purpose-skill', 'Join instructions.'))
    sibling = expertise.put(ctx, 'code.sibling', 'sibling-skill', document('sibling-skill', 'Sibling instructions.'))
    assert {item['id'] for item in expertise.catalog(ctx, 'code.receiver')} == {receiver['id'], joined_skill['id']}
    assert {item['id'] for item in expertise.catalog(ctx, 'code.provider')} == {joined_skill['id']}
    assert {item['id'] for item in expertise.catalog(ctx, f'join:{joined.id}')} == {receiver['id'], joined_skill['id']}
    assert expertise.catalog(ctx, 'code') == []
    assert expertise.catalog(ctx, 'code.sibling') == [sibling]
    assert expertise.catalog(ctx) == []
    with pytest.raises(Stop, match='No project agent skill'):
        expertise.read(ctx, joined_skill['id'], 'code.sibling')


def test_selected_body_and_graph_snapshot_are_exact_after_edit(project):
    ctx, store, _, base = project
    before = store.layer_graph(base.name)
    made = expertise.put(ctx, 'code.receiver', 'exact-cpp', document('exact-cpp', 'First instructions.'))
    body = document('exact-cpp', '\n  Keep this exact body, {project}, symbols <&>, and punctuation.\n',
                    license='MIT', metadata={'owner': 'Project team'}, compatibility='Use the project tools.')
    edited = expertise.put(ctx, 'code.receiver', 'exact-cpp', body, 'Updated description.', made['id'])
    assert edited['id'] == made['id']
    read = expertise.read(ctx, made['id'], 'code.receiver')
    assert read['name'] == 'exact-cpp'
    assert read['text'] == read['component']['text'] == body
    assert read['component']['rendered_fingerprint'] == hashlib.sha256(body.encode()).hexdigest()
    assert read['component']['source'] == {'kind': 'graph', 'layer': 'expertise',
                                          'node': 'code.receiver', 'item_id': made['id']}
    assert read['attachment'] == {'layer': 'expertise', 'node': 'code.receiver', 'item_id': made['id']}
    assert expertise.read(ctx, 'exact-cpp', 'code.receiver')['text'] == body
    assert store.layer_graph(base.name) == before


def test_exact_id_can_be_loaded_without_global_name_lookup(project):
    ctx, _, joined, _ = project
    made = expertise.put(ctx, f'join:{joined.id}', 'purpose-skill', document('purpose-skill', 'Only this selected body.'))
    assert expertise.read(ctx, made['id'])['text'] == document('purpose-skill', 'Only this selected body.')
    with pytest.raises(Stop, match='No project agent skill'):
        expertise.read(ctx, made['name'])
    ctx.nouns['node'] = 'code.provider'
    assert expertise.read(ctx, made['name'])['id'] == made['id']


def test_put_reuses_name_at_same_attachment_and_ambiguous_scoped_names_need_id(project):
    ctx, _, joined, _ = project
    first = expertise.put(ctx, 'code.receiver', 'same-name', document('same-name', 'First body.'))
    replaced = expertise.put(ctx, 'code.receiver', 'same-name', document('same-name', 'Updated body.'))
    assert replaced['id'] == first['id']
    second = expertise.put(ctx, f'join:{joined.id}', 'same-name', document('same-name', 'Distinct attachment.'))
    with pytest.raises(Stop, match='More than one'):
        expertise.read(ctx, 'same-name', 'code.receiver')
    assert expertise.read(ctx, first['id'], 'code.receiver')['text'] == document('same-name', 'Updated body.')
    assert expertise.read(ctx, second['id'], 'code.receiver')['text'] == document('same-name', 'Distinct attachment.')


def test_existing_layer_declaration_and_unrelated_items_are_preserved(project):
    ctx, store, _, _ = project
    store.layer('expertise', 'existing-owner', 'Existing canonical declaration.',
                mutable=True, hideable=False, tags=('existing-tag',), ready=True)
    original = store.layer_ref('expertise')
    store.add_item('expertise', Node('element', 'code.receiver'), 'Ordinary evidence.')
    expertise.put(ctx, 'code.receiver', 'scoped-skill', document('scoped-skill', 'Selected instructions.'))
    assert store.layer_ref('expertise') == original
    assert len(expertise.catalog(ctx, 'code.receiver')) == 1
    assert len(store.layer_items('expertise', limit=0).results) == 2


def test_invalid_target_and_non_skill_id_do_not_change_map(project):
    ctx, store, _, base = project
    before = store.layer_graph(base.name)
    with pytest.raises(Stop, match='No functional node'):
        expertise.put(ctx, 'code.MissingCanonicalNode', 'Name', document('Name', 'Instructions.'))
    assert not any(layer.name == 'expertise' for layer in store.layers(limit=0).results)
    expertise.put(ctx, 'code.receiver', 'valid', document('valid', 'Instructions.'))
    other = store.add_item('expertise', Node('element', 'code.receiver'), 'Not a skill.')
    with pytest.raises(Stop, match='No project agent skill'):
        expertise.read(ctx, other.id)
    assert store.layer_graph(base.name) == before


def test_skill_cannot_be_edited_through_a_different_attachment(project):
    ctx, _, _, _ = project
    made = expertise.put(ctx, 'code.receiver', 'unmoved-skill', document('unmoved-skill', 'Original body.'))
    with pytest.raises(Stop, match='No project agent skill'):
        expertise.put(ctx, 'code.sibling', 'unmoved-skill', document('unmoved-skill', 'Wrong attachment.'), skill_id=made['id'])
    assert expertise.read(ctx, made['id'])['text'] == document('unmoved-skill', 'Original body.')


def test_receiver_inline_joins_and_direct_join_documents_serialize_with_resources(project):
    ctx, store, joined, base = project
    before = store.layer_graph(base.name)
    text = document('combined-skill', 'Use the attached reference.\n',
                    **{'allowed-tools': ['Read', 'Edit'], 'metadata': {'version': 7}})
    files = {'references/example.txt': '  Exact reference <&>.\n'}
    receiver = expertise.put(ctx, 'code.receiver', 'combined-skill', text, files=files)
    direct = expertise.put(ctx, f'join:{joined.id}', 'combined-skill', text, files=files)
    stored = {item.id: item for item in store.layer_items('expertise', limit=0).results}
    inline = stored[receiver['id']].value
    assert set(inline) == {'joins'}
    assert len(inline['joins']) == 1
    for made, record in ((receiver, inline['joins'][0]), (direct, stored[direct['id']].value)):
        assert json.loads(json.dumps(record)) == record
        assert record['files'] == {'SKILL.md': text, **files}
        loaded = expertise.read(ctx, made['id'])
        assert expertise.read(ctx, loaded['uri'])['text'] == text
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
    assert receiver['uri'] == 'skill://expertise/code.receiver/combined-skill/SKILL.md'
    assert direct['uri'] == f'skill://expertise/{joined.id}/combined-skill/SKILL.md'
    assert store.layer_graph(base.name) == before


def test_plain_skill_body_requires_an_explicit_description(project):
    ctx, _, _, _ = project
    with pytest.raises(ValueError, match='description'):
        expertise.put(ctx, 'code.receiver', 'plain-skill', 'Body without frontmatter.')
    made = expertise.put(ctx, 'code.receiver', 'plain-skill', 'Body without frontmatter.', 'Explicit purpose.')
    loaded = expertise.read(ctx, made['id'])
    expected = skills.document('plain-skill', 'Body without frontmatter.', 'Explicit purpose.', uri=loaded['uri'])
    assert loaded['text'] == expected['files']['SKILL.md'].decode()
    assert loaded['frontmatter'] == expected['frontmatter']


def test_invalid_skill_name_is_not_silently_normalized(project):
    ctx, store, _, _ = project
    with pytest.raises(ValueError, match='Skill name'):
        expertise.put(ctx, 'code.receiver', 'Canonical Name',
                      document('Canonical Name', 'Keep exact authored spelling.'))
    assert expertise.catalog(ctx, 'code.receiver') == []
    assert not any(layer.name == 'expertise' for layer in store.layers(limit=0).results)


def test_resource_callback_serves_one_known_graph_document_with_identical_digests(project):
    ctx, _, joined, _ = project
    text = document('native-graph-skill', 'Load this exact document through the Skills extension.\n',
                    metadata={'source': 'project'})
    files = {'references/details.md': '# Exact reference\n'}
    made = expertise.put(ctx, f'join:{joined.id}', 'native-graph-skill', text, files=files)
    expected = skills.document('native-graph-skill', text, files=files, uri=made['uri'])
    assert expertise.resource(ctx, made['uri']) == expected
    assert expertise.resource(ctx, 'skill://some-other-skill/SKILL.md') is None
    assert expertise.resource(ctx, 'skill://expertise/code.receiver/not-present/SKILL.md') is None
    assert expertise.resource(ctx, 'skill://expertise/code.missing/not-present/SKILL.md') is None
    assert expertise.catalog(ctx) == []
