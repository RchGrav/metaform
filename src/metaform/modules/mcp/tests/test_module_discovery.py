"""Module authors extend discovery through declarations; clients load only the capability they need."""
import asyncio

import pytest

from metaform.modules.mcp import catalog, server
from metaform.modules.mcp.tests.test_mcp import mapped as mapped  # noqa: PLC0414
from metaform.modules.mcp.tests.test_mcp import session

pytestmark = pytest.mark.kind('fixture')


def text(result):
    return '\n'.join(one.text for one in result.contents)


def test_startup_only_lists_discovery_for_every_task_and_stateless_client(mapped, monkeypatch):
    for task in ('project_agent', 'user_agent', 'intake', 'composer', ''):
        monkeypatch.setenv('METAFORM_TASK_NAME', task)
        assert server.listed_names(mapped, None) == ('metaform_catalog',)
        assert server.listed_names(mapped, f'session-{task}') == ('metaform_catalog',)
        opening = server.connect_instructions(mapped)
        assert 'metaform://modules' in opening and 'metaform://tools' not in opening
    schema = server.catalog_schema(mapped)
    assert 'module' in schema['properties'] and 'category' not in schema['properties']
    assert 'enum' not in schema['properties']['module']  # no repeated inventory in every tool schema


def test_new_module_owns_its_tools_without_any_mcp_registry_entry(run, mapped, user_module):
    user_module('sound_lab', '''
        from metaform.module import Module, Verb, Noun
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        def measure(ctx):
            return {'frequency': ctx.nouns['frequency']}
        MODULE = Module(id='sound_lab', summary='Measure acoustic resonances.', purpose='Find sound defects.', verbs=(
            Verb('measure', measure, 'Measure a resonance.', effect='read', nouns=(Noun('frequency', 'Frequency in Hz.', 'int'),)),
        ))
    ''')
    run('enable', 'sound_lab', cwd=mapped)
    directory = server.modules_text(mapped)
    assert 'sound_lab: Measure acoustic resonances. — metaform://sound_lab/tools' in directory
    assert 'sound_lab_measure' not in directory
    commands = server.module_tools_text(mapped, 'sound_lab')
    assert 'sound_lab_measure(frequency' in commands
    assert 'map_work(' not in commands and 'memory_read_graph(' not in commands
    grouped = catalog.grouped(server.given_tools(mapped), server.tools(mapped))
    assert grouped['sound_lab'] == ['sound_lab_measure']
    assert sum('sound_lab_measure' in names for names in grouped.values()) == 1
    run('disable', 'sound_lab', cwd=mapped)
    assert 'metaform://sound_lab/tools' not in server.modules_text(mapped)
    with pytest.raises(server.Missing):
        server.module_tools_text(mapped, 'sound_lab')


def test_module_resource_selects_only_that_module_and_receipts_cross_catalog(mapped):
    async def read(uri, caller):
        return (await server.read_resource_text(mapped, uri, session=caller))[0]
    first = asyncio.run(read('metaform://memory/tools', 'module-reader'))
    assert 'memory_read_graph(' in first
    names = server.listed_names(mapped, 'module-reader')
    assert len(names) > 1 and all(name.startswith('memory_') or name == 'metaform_catalog' for name in names)
    again = server.run_catalog(mapped, {'module': 'memory'}, 'module-reader')[1][0]
    assert 'memory_read_graph(' not in again
    assert 'memory_read_graph(' in asyncio.run(read('metaform://memory/tools', 'other-reader'))
    server.run_catalog(mapped, {'module': 'map'}, 'module-reader')
    assert 'map_where' in server.listed_names(mapped, 'module-reader')
    assert 'memory_read_graph' not in server.listed_names(mapped, 'module-reader')
    server.run_catalog(mapped, {'module': 'memory'}, 'module-reader')
    assert 'memory_read_graph' in server.listed_names(mapped, 'module-reader')
    server.compaction_state(mapped, 'module-reader')
    assert 'memory_read_graph(' in asyncio.run(read('metaform://memory/tools', 'module-reader'))


def test_directory_is_retained_but_updates_when_modules_change(run, mapped):
    first = server.run_catalog(mapped, {}, 'directory-reader')[1][0]
    assert 'metaform://memory/tools' in first
    repeated = asyncio.run(server.read_resource_text(mapped, 'metaform://modules', session='directory-reader'))[0]
    assert 'metaform://memory/tools' not in repeated
    run('disable', 'memory', cwd=mapped)
    changed = server.run_catalog(mapped, {}, 'directory-reader')[1][0]
    assert 'metaform://map/tools' in changed and 'metaform://memory/tools' not in changed


def test_fuzzy_search_finds_misspelled_commands_and_returns_the_owning_module(mapped):
    error, blocks = server.run_catalog(mapped, {'module': 'memory', 'search': 'add obsrvations'}, 'search-reader')
    assert not error
    assert 'memory_add_observations(' in blocks[0] and '[metaform://memory/tools]' in blocks[0]
    assert 'map_' not in blocks[0]
    # Searching does not switch the caller's open module or execute a command.
    assert server.listed_names(mapped, 'search-reader') == ('metaform_catalog',)
    ranked = catalog.ranked('observe', {'a': 'observe', 'b': 'obsevre'}, {})
    assert ranked == ['a', 'b']
    assert catalog.ranked('xyzq', {'a': 'observe'}, {}) == []


def test_resource_opens_module_on_real_stdio_wire(home, mapped):
    async def exercise(client, init):
        initial = {one.name for one in (await client.list_tools()).tools}
        assert initial == {'metaform_catalog', 'project'}
        directory = text(await client.read_resource('metaform://modules'))
        assert 'metaform://map/tools' in directory and 'map_where(' not in directory
        resource = text(await client.read_resource('metaform://map/tools'))
        assert 'map_where(' in resource
        opened = {one.name for one in (await client.list_tools()).tools}
        assert 'map_where' in opened and 'memory_read_graph' not in opened
        response = await client.call_tool('metaform_catalog', {'tool': 'map_roots', 'arguments': {}})
        assert not response.is_error
        assert response.content
    session(home, mapped, exercise)
