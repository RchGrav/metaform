"""The settings screen edits the same settings as set and unset, and turns modules on and off."""
import asyncio

from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from metaform import home as metaform_home, loader, settings, tui


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
        assert asyncio.run(drive()) == set(settings.SCHEMA)


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
            screen._edit()
            screen.editor.text = 'other'
            screen._apply_edit()
            screen._toggle_pin()
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
                screen.module_index = [row['id'] for row in screen.rows].index('template')
                screen._toggle_module()
                screen._save_changes()
                await screen.last_task
            asyncio.run(drive())
        loader.reset()
        return next(item for item in loader.discover() if item.id == 'template').enabled
    assert toggle() is False
    assert toggle() is True
