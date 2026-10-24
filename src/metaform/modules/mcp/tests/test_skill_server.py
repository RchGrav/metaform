"""Standard Skills extension integrated with the real server's registered resource handlers."""
from __future__ import annotations

import base64
import hashlib
import json
from types import SimpleNamespace
from urllib.parse import quote

import anyio
import pytest
from mcp.shared.exceptions import MCPError

pytestmark = pytest.mark.kind('fixture')

TEXT = '''---
name: server-fixture
description: A complete fixture served over MCP.
metadata:
  authored-by: fixture author
---
PRIVATE_BODY_MARKER: load only after explicit resource retrieval.
Read [the reference](references/a%20guide%23.md).
'''
FILES = {'references/a guide#.md': 'PRIVATE_REFERENCE_MARKER: café.\r\n'.encode(),
         'assets/data.bin': b'\x00\xff\r\n\x01'}


@pytest.fixture
def served(project_folder):
    from metaform.loader import discover
    discover()
    from metaform import skills
    from metaform.modules.mcp import server, skill_extension

    skills.publish('server-fixture', TEXT, files=FILES)
    instance, _, _ = server.build(project_folder, http=True)
    ctx = SimpleNamespace(request=None, params={}, protocol_version='2026-07-28',
                          session=SimpleNamespace(client_capabilities=SimpleNamespace(extensions={}), client_params=None))
    return SimpleNamespace(instance=instance, ctx=ctx, module=server, extension=skill_extension,
                           folder=project_folder, skills=skills)


def invoke(served, method, arguments):
    entry = served.instance.get_request_handler(method)
    assert entry is not None
    params = entry.params_type.model_validate(arguments)

    async def call():
        return await entry.handler(served.ctx, params)
    return anyio.run(call)


def resource_bytes(served, uri):
    result = invoke(served, 'resources/read', {'uri': uri})
    content, = result.contents
    return content.text.encode('utf-8') if hasattr(content, 'text') else base64.b64decode(content.blob)


def test_real_server_advertises_extension_and_lists_manifests_without_bodies(served):
    assert served.instance.extensions[served.extension.EXTENSION] == {}
    capabilities = served.instance.create_initialization_options().capabilities
    assert capabilities.extensions[served.extension.EXTENSION] == {}
    assert capabilities.resources is not None
    listed = invoke(served, 'skills/list', {})
    assert listed['resultType'] == 'complete'
    entry = next(entry for entry in listed['skills'] if entry['uri'] == 'skill://server-fixture/SKILL.md')
    assert entry['frontmatter']['metadata'] == {'authored-by': 'fixture author'}
    assert len(entry['resources']) == 3
    metadata = invoke(served, 'resources/list', {})
    assert any(str(resource.uri) == entry['uri'] for resource in metadata.resources)
    disclosed = json.dumps(listed) + metadata.model_dump_json() + served.module.connect_instructions(served.folder)
    assert 'PRIVATE_BODY_MARKER' not in disclosed and 'PRIVATE_REFERENCE_MARKER' not in disclosed
    assert 'metaform_skills' not in served.module.listing(served.folder)


def test_real_resource_reads_match_every_raw_manifest_digest_and_size(served):
    uri = 'skill://server-fixture/SKILL.md'
    result = invoke(served, 'skills/get', {'uri': uri})
    assert result['resultType'] == 'complete'
    entry = result['skill']
    expected = {'SKILL.md': TEXT.encode(), **FILES}
    assert {resource['uri'] for resource in entry['resources']} == {
        'skill://server-fixture/' + quote(path, safe='/') for path in expected}
    for resource in entry['resources']:
        raw = resource_bytes(served, resource['uri'])
        assert resource['size'] == len(raw)
        assert resource['digest'] == 'sha256:' + hashlib.sha256(raw).hexdigest()
    assert resource_bytes(served, uri) == TEXT.encode()
    assert resource_bytes(served, 'skill://server-fixture/assets/data.bin') == FILES['assets/data.bin']


def test_graph_skill_supports_direct_standard_get_and_read_without_enumeration(served):
    from metaform.data import Store
    from metaform.module import context
    from metaform.modules.tasks import expertise

    store = Store('proj')
    with store.atomic():
        layer = store.layer('test-map', 'intake', 'Test map.', kind='intake', mutable=False,
                            hideable=False, provenance={'module': 'intake'}, ready=True)
        store.add_element(layer.name, 'code.receiver', name_length=1, role='DE')
    text = TEXT.replace('server-fixture', 'graph-fixture')
    ctx = context('tasks', served.folder)
    made = expertise.put(ctx, 'code.receiver', 'graph-fixture', text,
                         files={'references/details.md': 'Exact graph reference.'})
    uri = made['uri']
    assert uri.startswith('skill://expertise/')
    assert uri not in {entry['uri'] for entry in invoke(served, 'skills/list', {})['skills']}
    assert uri not in {str(resource.uri) for resource in invoke(served, 'resources/list', {}).resources}
    entry = invoke(served, 'skills/get', {'uri': uri})['skill']
    assert entry['frontmatter']['name'] == 'graph-fixture'
    assert resource_bytes(served, uri) == text.encode()
    assert resource_bytes(served, uri.removesuffix('SKILL.md') + 'references/details.md') == b'Exact graph reference.'
    for resource in entry['resources']:
        assert resource['digest'] == 'sha256:' + hashlib.sha256(resource_bytes(served, resource['uri'])).hexdigest()


@pytest.mark.parametrize('method', ['skills/get', 'resources/read'])
def test_real_server_unknown_skill_uri_returns_invalid_params(served, method):
    with pytest.raises(MCPError) as caught:
        invoke(served, method, {'uri': 'skill://unknown/SKILL.md'})
    assert caught.value.code == -32602
