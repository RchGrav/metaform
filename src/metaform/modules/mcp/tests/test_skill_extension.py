"""Skills manifests and on-demand file reads through registered low-level MCP handlers."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import anyio
import pytest
from mcp.server.lowlevel import Server
from mcp.shared.exceptions import MCPError
from pydantic import ValidationError

pytestmark = pytest.mark.kind('fixture')

TEXT = '''---
name: fixture-skill
description: Read the exact supplied fixture.
license: MIT
allowed-tools: fixture_read
metadata:
  fixture-owner: "Original Author"
  nested:
    value: 7
---
Read [the reference](references/details.md) before using the fixture.
'''
FILES = {'references/details.md': 'Exact reference: café.\r\n'.encode(),
         'assets/data.bin': b'\x00\xff\x01\r\n'}


@pytest.fixture
def extension(home, tmp_path, monkeypatch):
    from metaform import skills
    from metaform.modules.mcp import skill_extension

    monkeypatch.setattr(skill_extension, 'provided', lambda folder, kind: [])
    served = Server('fixture')
    skill_extension.register(served, tmp_path)
    return SimpleNamespace(server=served, module=skill_extension, skills=skills, folder=tmp_path)


def invoke(extension, method, arguments):
    entry = extension.server.get_request_handler(method)
    assert entry is not None
    params = entry.params_type.model_validate(arguments)

    async def call():
        return await entry.handler(None, params)
    return anyio.run(call)


def published(extension):
    return extension.skills.publish('fixture-skill', TEXT, files=FILES)


def test_complete_entry_preserves_frontmatter_and_every_file_digest_without_bodies(extension):
    published(extension)
    listed = invoke(extension, 'skills/list', {})
    assert listed['resultType'] == 'complete'
    assert listed['ttlMs'] == 0 and listed['cacheScope'] == 'private'
    assert extension.server.extensions[extension.module.EXTENSION] == {}
    entry, = listed['skills']
    assert entry['uri'] == 'skill://fixture-skill/SKILL.md'
    assert entry['frontmatter'] == {
        'name': 'fixture-skill', 'description': 'Read the exact supplied fixture.', 'license': 'MIT',
        'allowed-tools': 'fixture_read', 'metadata': {'fixture-owner': 'Original Author', 'nested': {'value': 7}}}
    assert set(entry) == {'uri', 'frontmatter', 'resources'}
    expected = {'SKILL.md': TEXT.encode(), **FILES}
    manifest = {resource['uri']: resource for resource in entry['resources']}
    assert set(manifest) == {f'skill://fixture-skill/{path}' for path in expected}
    for path, raw in expected.items():
        uri = f'skill://fixture-skill/{path}'
        assert manifest[uri] == {'uri': uri, 'digest': 'sha256:' + hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
        actual, mime = extension.module.read(extension.folder, uri)
        assert actual == raw
        assert mime == ('text/markdown' if path.endswith('.md') else 'application/octet-stream')
    metadata, = extension.module.resources(extension.folder)
    assert metadata == {'uri': entry['uri'], 'name': 'fixture-skill',
                        'description': entry['frontmatter']['description'], 'mime_type': 'text/markdown'}


def test_direct_get_and_reads_work_without_listing_or_graph_enumeration(extension, monkeypatch):
    published(extension)
    monkeypatch.setattr(extension.module, 'entries', lambda folder: [])
    assert invoke(extension, 'skills/list', {})['skills'] == []
    result = invoke(extension, 'skills/get', {'uri': 'skill://fixture-skill/SKILL.md'})
    assert result['resultType'] == 'complete' and result['skill']['frontmatter']['name'] == 'fixture-skill'
    assert result['ttlMs'] == 0 and result['cacheScope'] == 'private'
    assert extension.module.read(extension.folder, 'skill://fixture-skill/references/details.md')[0] == \
        FILES['references/details.md']


def test_pages_keep_complete_entries_atomic(extension, monkeypatch):
    published(extension)
    entry = invoke(extension, 'skills/get', {'uri': 'skill://fixture-skill/SKILL.md'})['skill']
    entries = [{**entry, 'uri': f'skill://fixture-{index}/SKILL.md'} for index in range(3)]
    monkeypatch.setattr(extension.module, 'entries', lambda folder: entries)
    monkeypatch.setattr(extension.module, 'PAGE_SIZE', 2)
    first = invoke(extension, 'skills/list', {})
    assert first['skills'] == entries[:2] and first['nextCursor'] == '2'
    second = invoke(extension, 'skills/list', {'cursor': first['nextCursor']})
    assert second['skills'] == entries[2:] and 'nextCursor' not in second


@pytest.mark.parametrize('cursor', ['', '-1', '1.5', '١', '99999999999999999999999999', '1'])
def test_invalid_list_cursors_return_invalid_params(extension, cursor):
    with pytest.raises(MCPError) as caught:
        invoke(extension, 'skills/list', {'cursor': cursor})
    assert caught.value.code == -32602


@pytest.mark.parametrize('uri', ['skill://unknown/SKILL.md', 'skill://fixture-skill/references/details.md',
                                 'https://elsewhere.invalid/fixture-skill/SKILL.md', 'fixture-skill'])
def test_unknown_or_non_skill_get_uri_returns_invalid_params(extension, uri):
    published(extension)
    with pytest.raises(MCPError) as caught:
        invoke(extension, 'skills/get', {'uri': uri})
    assert caught.value.code == -32602


def test_missing_uri_is_a_request_validation_error(extension):
    with pytest.raises(ValidationError):
        invoke(extension, 'skills/get', {})


@pytest.mark.parametrize('uri', ['skill://fixture-skill/../outside', 'skill://fixture-skill/missing.md',
                                 'skill://fixture-skill/SKILL.md?changed=1', 'https://elsewhere.invalid/SKILL.md'])
def test_unknown_supporting_files_are_not_read(extension, uri):
    published(extension)
    assert extension.module.read(extension.folder, uri) is None


@pytest.mark.parametrize('uri', ['skill://skills/code.Unchanged_Node/fixture-skill/SKILL.md',
                               'skill://fixture-skill/SKILL.md'])
def test_known_provider_document_is_loadable_without_enumerating_graph_content(extension, monkeypatch, uri):
    bundle = extension.skills.document('fixture-skill', TEXT, files=FILES, uri=uri)
    provider_ctx = object()
    requested = []

    def resolve(ctx, requested_uri):
        assert ctx is provider_ctx
        requested.append(requested_uri)
        return bundle if requested_uri == uri else None

    def provided(folder, kind):
        assert folder == extension.folder and kind == 'skill.document'
        return [('fixture-provider', resolve)]

    def context(owner, folder, **kwargs):
        assert owner == 'fixture-provider' and folder == extension.folder and kwargs == {'surface': 'mcp'}
        return provider_ctx

    monkeypatch.setattr(extension.module, 'provided', provided)
    monkeypatch.setattr(extension.module, 'context', context)
    assert invoke(extension, 'skills/list', {})['skills'] == []
    assert extension.module.resources(extension.folder) == []
    assert requested == []
    entry = invoke(extension, 'skills/get', {'uri': uri})['skill']
    assert entry == {key: bundle[key] for key in ('uri', 'frontmatter', 'resources')}
    root_resource = next(resource for resource in entry['resources'] if resource['uri'] == uri)
    assert root_resource['digest'] == 'sha256:' + hashlib.sha256(TEXT.encode()).hexdigest()
    assert extension.module.read(extension.folder, uri) == (TEXT.encode(), 'text/markdown')
    reference = uri.removesuffix('SKILL.md') + 'references/details.md'
    assert extension.module.read(extension.folder, reference) == (FILES['references/details.md'], 'text/markdown')
    assert set(requested) == {uri, uri.removesuffix('SKILL.md') + 'references/SKILL.md'}
    assert invoke(extension, 'skills/list', {})['skills'] == []
