"""Authored skill bytes and manifests are shared by MCP and the receiver-owned skill layer."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from metaform import skills

pytestmark = [pytest.mark.kind('fixture')]


def test_authored_frontmatter_and_exact_bytes_survive_document_creation():
    source = ('---\r\nname: node-guide\r\ndescription: Guide the receiving node.\r\n'
              'license: MIT\r\nmetadata:\r\n  author: developer\r\n  revision: "2"\r\n'
              'future-field:\r\n  enabled: true\r\n  values: [1, null, "é"]\r\n---\r\n'
              '\r\n# Guide\r\nKeep this spacing.  \r\n')
    bundle = skills.document('node-guide', source, files={'references/guide.md': 'café\n', 'assets/icon.bin': b'\x00\xff'})
    assert bundle['frontmatter'] == {
        'name': 'node-guide', 'description': 'Guide the receiving node.', 'license': 'MIT',
        'metadata': {'author': 'developer', 'revision': '2'},
        'future-field': {'enabled': True, 'values': [1, None, 'é']},
    }
    assert bundle['files'] == {
        'SKILL.md': source.encode('utf-8'), 'references/guide.md': b'caf\xc3\xa9\n', 'assets/icon.bin': b'\x00\xff',
    }
    expected = []
    for relative, raw in sorted(bundle['files'].items()):
        expected.append({'uri': f'skill://node-guide/{relative}',
                         'digest': 'sha256:' + hashlib.sha256(raw).hexdigest(), 'size': len(raw)})
    assert bundle['uri'] == 'skill://node-guide/SKILL.md'
    assert bundle['resources'] == expected


def test_plain_body_is_preserved_after_generated_header_and_requires_authored_description():
    body = '\n  Do exactly this.\r\n\n'
    bundle = skills.document('node-guide', body, 'Guide the receiving node.')
    assert bundle['files']['SKILL.md'].split(b'---\n', 2)[2] == body.encode('utf-8')
    assert skills.document('node-guide', bundle['files']['SKILL.md'].decode()) == bundle
    with pytest.raises(ValueError, match='description'):
        skills.document('node-guide', body)


@pytest.mark.parametrize('source', [
    '---\nname: node-guide\ndescription: Missing delimiter.\n',
    '---\nname: node-guide\ndescription: [unclosed\n---\nBody',
    '---\n- name\n- description\n---\nBody',
    '---\nname: another-name\ndescription: Mismatched name.\n---\nBody',
    '---\nname: node-guide\n---\nBody',
    '---\nname: node-guide\ndescription: 3\n---\nBody',
    '---\nname: node-guide\ndescription: "   "\n---\nBody',
    '---\nname: node-guide\nname: node-guide\ndescription: Duplicate key.\n---\nBody',
    '---\nname: node-guide\ndescription: Invalid JSON.\nextra: .nan\n---\nBody',
])
def test_malformed_or_inconsistent_frontmatter_is_rejected(source):
    with pytest.raises(ValueError):
        skills.document('node-guide', source)


@pytest.mark.parametrize('name', ['', 'Node-guide', 'node_guide', 'node guide', '-node', 'node-', 'node--guide', 'x' * 65])
def test_invalid_skill_names_are_rejected_without_rewriting(name):
    with pytest.raises(ValueError, match='Skill name'):
        skills.document(name, 'Body', 'Description')


def test_hierarchical_uri_and_supporting_filenames_have_unambiguous_resource_addresses():
    bundle = skills.document('node-guide', 'Body', 'Description',
                             files={'references/a guide#.md': 'Guide'},
                             uri='skill://metaform/expertise/node-guide/SKILL.md')
    assert bundle['uri'] == 'skill://metaform/expertise/node-guide/SKILL.md'
    assert {one['uri'] for one in bundle['resources']} == {
        'skill://metaform/expertise/node-guide/SKILL.md',
        'skill://metaform/expertise/node-guide/references/a%20guide%23.md',
    }


@pytest.mark.parametrize('uri', [
    'https://node-guide/SKILL.md', 'skill://another-name/SKILL.md', 'skill:///node-guide/SKILL.md',
    'skill://metaform/../node-guide/SKILL.md', 'skill://metaform//node-guide/SKILL.md',
    'skill://metaform/%2e%2e/node-guide/SKILL.md', 'skill://node-guide/SKILL.md?next=other',
    'skill://node-guide/SKILL.md#fragment', 'skill://other@node-guide/SKILL.md',
    'skill://node-guide/SKILL.md?', 'skill://node-guide/SKILL.md#', 'skill://node-guide/SKILL.md\n',
])
def test_uris_cannot_silently_change_origin_or_skill_directory(uri):
    with pytest.raises(ValueError):
        skills.document('node-guide', 'Body', 'Description', uri=uri)


@pytest.mark.parametrize('path', [
    '', '/outside.md', '../outside.md', 'references/../../outside.md', 'references/./guide.md',
    'references//guide.md', 'references\\guide.md', 'references/%2e%2e/outside.md',
    'skill://other/SKILL.md', 'https://other/guide.md', 'C:/outside.md', 'references/guide.md\x00',
])
def test_support_files_cannot_escape_the_skill_directory(path):
    with pytest.raises(ValueError):
        skills.document('node-guide', 'Body', 'Description', files={path: 'Outside'})


def test_conflicting_skill_source_and_file_directory_collisions_are_rejected():
    bundle = skills.document('node-guide', 'Body', 'Description')
    source = bundle['files']['SKILL.md']
    assert skills.document('node-guide', source.decode(), files={'SKILL.md': source}) == bundle
    assert len(bundle['resources']) == 1
    with pytest.raises(ValueError, match='Conflicting SKILL.md'):
        skills.document('node-guide', source.decode(), files={'SKILL.md': b'Different'})
    with pytest.raises(ValueError, match='directory'):
        skills.document('node-guide', 'Body', 'Description', files={'references': b'', 'references/guide.md': b''})


def test_manifest_accepts_exact_file_count_limit_and_rejects_one_more():
    files = {f'assets/{number}.txt': b'' for number in range(511)}
    assert len(skills.document('node-guide', 'Body', 'Description', files=files)['resources']) == 512
    files['assets/extra.txt'] = b''
    with pytest.raises(ValueError, match='512 files'):
        skills.document('node-guide', 'Body', 'Description', files=files)


def test_manifest_size_limit_counts_raw_bytes_including_skill_source():
    source_size = len(skills.document('node-guide', 'Body', 'Description')['files']['SKILL.md'])
    remaining = 16 * 1024 * 1024 - source_size
    bundle = skills.document('node-guide', 'Body', 'Description', files={'assets/large.bin': b'\x00' * remaining})
    assert sum(one['size'] for one in bundle['resources']) == 16 * 1024 * 1024
    with pytest.raises(ValueError, match='16 MiB'):
        skills.document('node-guide', 'Body', 'Description', files={'assets/large.bin': b'\x00' * (remaining + 1)})


def test_reusable_publication_survives_readback_and_lists_metadata_without_content(tmp_path, monkeypatch):
    root = tmp_path / 'metaform-home'
    monkeypatch.setenv('METAFORM_HOME', str(root))
    assert skills.reusable_catalog() == []
    assert skills.reusable('node-guide') is None
    source = '---\r\nname: node-guide\r\ndescription: Guide the node.\r\ncustom: [keep, me]\r\n---\r\nBody  \r\n'
    bundle = skills.publish('node-guide', source, files={'references/guide.md': 'é\n', 'assets/data': b'\xff'})
    assert (root / 'skills/node-guide/SKILL.md').read_bytes() == source.encode('utf-8')
    assert skills.reusable('node-guide') == bundle
    assert skills.reusable('skill://node-guide/SKILL.md') == bundle
    assert skills.reusable_catalog() == [{key: bundle[key] for key in ('uri', 'frontmatter', 'resources')}]


def test_republishing_replaces_the_complete_skill_file_set_and_preserves_other_skills(tmp_path, monkeypatch):
    monkeypatch.setenv('METAFORM_HOME', str(tmp_path))
    skills.publish('node-guide', 'Old body', 'Old description', files={'references/stale.md': 'Old reference'})
    neighbor = skills.publish('other-guide', 'Other body', 'Other description')
    updated = skills.publish('node-guide', 'New body', 'New description', files={'references/current.md': b'Current'})
    assert skills.reusable('node-guide') == updated
    assert not (tmp_path / 'skills/node-guide/references/stale.md').exists()
    assert skills.reusable('other-guide') == neighbor
    with pytest.raises(ValueError):
        skills.publish('node-guide', 'Invalid body without description')
    assert skills.reusable('node-guide') == updated


def test_reusable_reads_reject_symbolic_links_to_content_outside_the_skill(tmp_path, monkeypatch):
    monkeypatch.setenv('METAFORM_HOME', str(tmp_path / 'home'))
    skills.publish('node-guide', 'Body', 'Description')
    outside = tmp_path / 'outside.md'
    outside.write_bytes(b'Outside this skill')
    (tmp_path / 'home/skills/node-guide/reference.md').symlink_to(outside)
    with pytest.raises(ValueError, match='symbolic links'):
        skills.reusable('node-guide')


def test_failed_publication_restores_the_previous_skill(tmp_path, monkeypatch):
    monkeypatch.setenv('METAFORM_HOME', str(tmp_path))
    original = skills.publish('node-guide', 'Original body', 'Original description', files={'reference.md': 'Keep'})
    replace = Path.replace

    def fail_staging_publication(path, target):
        if path.name == 'content':
            raise OSError('Simulated publication failure')
        return replace(path, target)

    monkeypatch.setattr(Path, 'replace', fail_staging_publication)
    with pytest.raises(OSError, match='Simulated publication failure'):
        skills.publish('node-guide', 'Replacement body', 'Replacement description')
    assert skills.reusable('node-guide') == original


@pytest.mark.parametrize('value', ['../node-guide', 'node_guide', 'skill://metaform/node-guide/SKILL.md',
                                   'https://node-guide/SKILL.md'])
def test_reusable_lookup_never_substitutes_a_different_origin(tmp_path, monkeypatch, value):
    monkeypatch.setenv('METAFORM_HOME', str(tmp_path))
    skills.publish('node-guide', 'Body', 'Description')
    with pytest.raises(ValueError):
        skills.reusable(value)
