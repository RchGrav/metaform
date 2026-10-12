"""The settings screen edits the same settings as set and unset, and turns modules on and off."""
import asyncio

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from metaform import home as metaform_home
from metaform import loader, settings, tui

pytestmark = [pytest.mark.kind('fixture'), pytest.mark.req('CLI-026')]


def _screen(folder):
    pipe = create_pipe_input()
    return pipe, tui.ChassisTUI(tui._Backend(folder), input=pipe, output=DummyOutput())


def test_screen_shows_every_setting_in_the_schema(home, tmp_path):
    pipe, screen = _screen(tmp_path)
    with pipe:
        async def drive():
            await screen.refresh()
            shown = set()
            for index, row in enumerate(screen.rows):
                screen.module_index = index
                shown |= {item.key for item in screen.declared_settings}
            return shown
        shown = asyncio.run(drive())
    # Every setting of the chassis and of each loaded module; a disabled module another test imported in this process
    # has settings in the schema that the screen rightly does not show.
    loaded = {'chassis'} | {item.id for item in loader.discover() if item.module is not None}
    assert shown == {key for key, item in settings.SCHEMA.items() if item.owner in loaded}


def test_screen_edits_and_glues_through_its_own_keys(home, tmp_path):
    work, other = tmp_path / 'work', tmp_path / 'other'
    work.mkdir(); other.mkdir()
    metaform_home.add_project('work', work)
    metaform_home.add_project('other', other)
    pipe, screen = _screen(work)
    with pipe:
        async def drive():
            await screen.refresh()
            screen._focus('settings')
            screen.setting_index = [item.key for item in screen.declared_settings].index('project')
            screen._edit()  # a choice setting opens the picker on its choices
            screen.pick_index = screen.pick_choices.index('other')
            screen._pick_apply()
            screen._toggle_glue()
            screen._save_changes()
            await screen.last_task
        asyncio.run(drive())
    assert settings.value('project', work) == 'other'
    assert settings.state('project', work) == 'glued'


def test_screen_turns_a_module_off_and_on(home, tmp_path):
    def toggle():
        pipe, screen = _screen(tmp_path)
        with pipe:
            async def drive():
                await screen.refresh()
                screen.module_index = [row.id for row in screen.rows].index('template')
                screen._toggle_module()
                screen._save_changes()
                await screen.last_task
            asyncio.run(drive())
        loader.reset()
        return next(item for item in loader.discover() if item.id == 'template').enabled
    first = toggle()
    assert toggle() is not first


@pytest.mark.req('CLI-031')
def test_screen_rows_read_as_config_show_rows(home, tmp_path, capsys):
    from metaform import cli
    settings.assign('debug', True, tmp_path)
    settings.assign('report', False, tmp_path, glue=True)
    assert cli.main(['config', '--show', f'folder={tmp_path}']) == 0
    expected = {line.split(':')[0].lstrip('* '): line for line in capsys.readouterr().out.splitlines() if ': ' in line}
    pipe, screen = _screen(tmp_path)
    with pipe:
        async def drive():
            await screen.refresh()
            screen.module_index = [row.id for row in screen.rows].index('chassis')
            return [text for _, text in screen._setting_lines()]
        rows = asyncio.run(drive())
    for key in ('debug', 'report', 'layers', 'modules'):
        assert any(row.rstrip('\n').endswith(expected[key]) for row in rows), (key, expected[key], rows)



@pytest.mark.req('BASE-037')
@pytest.mark.req('BASE-018')
def test_refreshing_the_screen_starts_no_module_again(home, tmp_path, user_module):
    marks = tmp_path / 'starts.txt'
    user_module('counted', f'''
        from pathlib import Path
        from metaform.module import Module
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        def start(ctx):
            with Path({str(marks)!r}).open('a') as out:
                out.write('start\\n')
        MODULE = Module(id='counted', summary='Counts.', purpose='Counts. Details: metaform help counted.',
                        start=start)
    ''')
    loader.reset()
    pipe, screen = _screen(tmp_path)
    with pipe:
        async def drive():
            for _ in range(3):
                await screen.refresh()
        asyncio.run(drive())
    assert marks.read_text().splitlines() == ['start']


@pytest.mark.req('BASE-009')
@pytest.mark.req('BASE-018')
def test_the_screen_loads_and_turns_off_a_module_whose_start_and_stop_are_async(home, tmp_path, user_module):
    marks = tmp_path / 'marks.txt'
    user_module('asyncer', f'''
        from pathlib import Path
        from metaform.module import Module
        SUPPORTED_OS = ('linux', 'macos', 'windows')
        async def start(ctx):
            with Path({str(marks)!r}).open('a') as out:
                out.write('start\\n')
        async def stop(ctx):
            with Path({str(marks)!r}).open('a') as out:
                out.write('stop\\n')
        MODULE = Module(id='asyncer', summary='Async.', purpose='Async. Details: metaform help asyncer.',
                        start=start, stop=stop)
    ''')
    loader.reset()
    pipe, screen = _screen(tmp_path)
    with pipe:
        async def drive():
            await screen.refresh()
            assert 'asyncer' not in screen.backend.load_errors
            screen.module_index = [row.id for row in screen.rows].index('asyncer')
            screen._toggle_module()
            screen._save_changes()
            await screen.last_task
        asyncio.run(drive())
    assert marks.read_text().splitlines() == ['start', 'stop']
    assert next(item for item in loader.discover() if item.id == 'asyncer').problem == ''


@pytest.mark.req('CLI-031')
def test_choices_are_picked_from_a_list_and_stepped_with_left_and_right(home, tmp_path):
    work, other = tmp_path / 'work', tmp_path / 'other'
    work.mkdir(); other.mkdir()
    metaform_home.add_project('work', work)
    metaform_home.add_project('other', other)
    pipe, screen = _screen(work)
    with pipe:
        async def drive():
            await screen.refresh()
            screen._focus('settings')
            keys = [item.key for item in screen.declared_settings]
            screen.setting_index = keys.index('modules')
            screen._edit()  # the modules setting opens as a checklist of every group, all checked while empty
            assert screen.picking and 'map' in screen.pick_choices and screen.pick_checked == set(screen.pick_choices)
            screen._pick_check(everything=True)
            screen.pick_index = screen.pick_choices.index('map')
            screen._pick_check()
            screen._pick_apply()
            screen.setting_index = keys.index('project')
            screen._side(1)  # → steps a choice setting instead of switching panels
            assert screen.panel == 'settings'
            screen._save_changes()
            await screen.last_task
        asyncio.run(drive())
    assert settings.value('modules', work) == ['map']
    assert settings.value('project', work) == 'other'


@pytest.mark.req('CLI-019')
def test_a_list_of_one_value_per_name_unchecks_the_others_of_a_name_when_one_is_checked(home, tmp_path):
    pipe, screen = _screen(tmp_path)
    with pipe:
        listed = settings.Setting(key='probe_options', kind='list', exclusive='=')
        screen.pick_target = ('probe', listed)
        screen.pick_choices = ['claude.model=small', 'claude.model=large', 'codex.model=small']
        screen.pick_checked = {'claude.model=small', 'codex.model=small'}
        screen.pick_index = 1
        screen._pick_check()
        assert screen.pick_checked == {'claude.model=large', 'codex.model=small'}
        screen._pick_check()
        assert screen.pick_checked == {'codex.model=small'}, 'unchecking leaves the name with none'
