"""Module authors extend discovery through declarations; clients load only the capability they need."""

import pytest

from metaform.modules.mcp import catalog, server
from metaform.modules.mcp.tests.test_mcp import mapped as mapped  # noqa: PLC0414

pytestmark = pytest.mark.kind('fixture')


def text(result):
    return '\n'.join(one.text for one in result.contents)


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
